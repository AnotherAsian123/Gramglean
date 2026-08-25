"""Executes one job: resolve links -> fetch full post metadata -> download.

Runs on a worker thread. Fetching is sequential with a randomized delay
between posts (rate limiting) and LRU cookie rotation on auth/rate-limit
errors, falling back to anonymous fetching when no cookie works. Downloads
run in a thread pool with retry + backoff.
"""
from __future__ import annotations

import logging
import os
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import httpx

from ..core import config
from ..core.logging_setup import (
    failed_downloads_handler,
    job_error_log_path,
    job_log_path,
)
from ..core.settings_service import EffectiveSettings
from ..db.database import session_scope
from ..db.models import Job, Link, Media, utcnow
from ..insta import client as ig
from ..insta import cookies as cookiestore
from .broker import broker
from .errors import summarise_error, write_failure_detail
from .metadata import embed_exif, metadata_payload

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".heic"}
_VIDEO_EXTS = {".mp4", ".mov", ".webm"}


class Cancelled(Exception):
    pass


class JobRunner:
    def __init__(self, job_id: int, settings: EffectiveSettings, cancel: threading.Event):
        self.job_id = job_id
        self.settings = settings
        self._cancel = cancel
        self._counter_lock = threading.Lock()
        self.total = 0
        self.downloaded = 0
        self.skipped = 0
        self.failed = 0
        self._log: logging.Logger = logging.getLogger(__name__)
        self._err: logging.Logger = logging.getLogger(__name__)
        self._handlers: list[logging.Handler] = []

    # ---- lifecycle -------------------------------------------------------

    def run(self) -> None:
        self._setup_loggers()
        try:
            self._update_job(status="running", started_at=utcnow())
            self._emit_progress("running")
            links = self._load_links()
            tasks = self._fetch_all(links)
            if tasks:
                self._download_all(tasks)
            self._mark_links_done()
            self._finish("completed")
        except Cancelled:
            self._mark_links_done()
            self._finish("cancelled")
        except Exception as exc:  # job-level failure
            summary = summarise_error(exc)
            write_failure_detail(
                self._err, job_id=self.job_id, context="job aborted", exc=exc
            )
            self._log.error("Job failed: %s: %s", type(exc).__name__, exc)
            self._finish("failed", error=summary)
        finally:
            self._teardown_loggers()

    def _setup_loggers(self) -> None:
        # Plain Logger instances (not in the global registry) so re-runs and
        # crashes can never accumulate handlers on shared loggers.
        self._log = logging.Logger(f"job.{self.job_id}")
        activity = logging.FileHandler(job_log_path(self.job_id))
        activity.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s"))
        self._log.addHandler(activity)

        self._err = logging.Logger(f"job.{self.job_id}.errors")
        per_job = logging.FileHandler(job_error_log_path(self.job_id))
        per_job.setFormatter(logging.Formatter("%(message)s"))
        shared = failed_downloads_handler()
        self._err.addHandler(per_job)
        self._err.addHandler(shared)

        self._handlers = [activity, per_job, shared]

    def _teardown_loggers(self) -> None:
        for handler in self._handlers:
            handler.close()
        self._handlers = []

    # ---- phase 1: fetch post metadata ------------------------------------

    def _fetch_all(self, links: list[Link]) -> list[dict]:
        """Resolve every link to concrete download tasks, rotating cookies."""
        tasks: list[dict] = []
        tried_cookies: set[int] = set()
        cookie = cookiestore.next_cookie(tried_cookies)
        http = self._build_client(cookie)
        try:
            for i, link in enumerate(links):
                self._check_cancel()
                if i > 0:
                    self._sleep_rate_limit()
                self._set_link(link.id, status="fetching")
                while True:
                    try:
                        info = ig.fetch_post(http, link.shortcode, authenticated=cookie is not None)
                        break
                    except (ig.RateLimited, ig.LoginRequired) as exc:
                        if cookie is not None:
                            status = "rate_limited" if isinstance(exc, ig.RateLimited) else "invalid"
                            cookiestore.mark_status(cookie.id, status, str(exc))
                            self._log.warning(
                                "Cookie '%s' %s; rotating", cookie.original_name, status
                            )
                            tried_cookies.add(cookie.id)
                            cookie = cookiestore.next_cookie(tried_cookies)
                            http.close()
                            http = self._build_client(cookie)
                            if cookie is None:
                                self._log.info("No cookies left; continuing anonymously")
                            continue
                        # Anonymous and still refused: this link fails.
                        self._fail_link(link, exc)
                        info = None
                        break
                    except ig.FetchError as exc:
                        self._fail_link(link, exc)
                        info = None
                        break
                    except httpx.HTTPError as exc:
                        self._fail_link(link, exc)
                        info = None
                        break
                if info is None:
                    continue
                if cookie is not None:
                    cookiestore.mark_status(cookie.id, "ok", None)
                new_items = self._plan_downloads(link, info)
                tasks.extend(new_items)
                self._log.info(
                    "Fetched %s: %d item(s), %d new",
                    link.shortcode, len(info.items), len(new_items),
                )
        finally:
            http.close()
        if cookie is not None:
            cookiestore.mark_used(cookie.id)
            self._update_job(cookie_used=cookie.original_name)
        return tasks

    def _build_client(self, cookie) -> httpx.Client:
        jar = None
        if cookie is not None:
            try:
                jar = cookiestore.load_cookie_jar(cookie)
            except Exception as exc:
                self._log.warning(
                    "Could not read cookie '%s': %s", cookie.original_name, exc
                )
                cookiestore.mark_status(cookie.id, "invalid", str(exc))
                jar = None
        return ig.build_http_client(jar)

    def _plan_downloads(self, link: Link, info: ig.PostInfo) -> list[dict]:
        """Turn a PostInfo into download tasks, skipping archived items."""
        with session_scope() as session:
            from sqlmodel import select

            existing = set(
                session.exec(
                    select(Media.child_index).where(Media.shortcode == link.shortcode)
                ).all()
            )
        tasks = []
        skipped_here = 0
        for item in info.items:
            if item.index in existing:
                skipped_here += 1
                continue
            tasks.append({"link": link, "info": info, "item": item})
        with self._counter_lock:
            self.total += len(info.items)
            self.skipped += skipped_here
        self._set_link(
            link.id,
            status="skipped" if not tasks else "fetching",
            username=info.username,
            caption=(info.caption or "")[:500] or None,
            taken_at=info.taken_at,
            media_count=len(info.items),
        )
        if not tasks and skipped_here:
            self._log.info("%s already fully archived; skipping", link.shortcode)
        self._persist_counters()
        self._emit_progress("running")
        return tasks

    def _fail_link(self, link: Link, exc: BaseException) -> None:
        summary = summarise_error(exc)
        write_failure_detail(
            self._err,
            job_id=self.job_id,
            context=f"fetch shortcode={link.shortcode} url={link.url}",
            exc=exc,
        )
        self._log.error("Fetch failed for %s: %s", link.shortcode, exc)
        self._set_link(link.id, status="failed", error=summary)
        with self._counter_lock:
            self.failed += 1
        self._persist_counters()
        self._emit_progress("running")

    # ---- phase 2: download -----------------------------------------------

    def _download_all(self, tasks: list[dict]) -> None:
        self._log.info("Downloading %d item(s) with %d thread(s)",
                       len(tasks), self.settings.download_threads)
        headers = {"User-Agent": config.USER_AGENT, "Referer": "https://www.instagram.com/"}
        with httpx.Client(headers=headers, timeout=config.REQUEST_TIMEOUT,
                          follow_redirects=True) as http:
            with ThreadPoolExecutor(max_workers=self.settings.download_threads) as pool:
                futures = {
                    pool.submit(self._download_one, http, t): t for t in tasks
                }
                for future in as_completed(futures):
                    task = futures[future]
                    try:
                        ok = future.result()
                    except Cancelled:
                        ok = None
                    except Exception as exc:
                        self._record_failure(task, exc)
                        ok = False
                    if ok:
                        with self._counter_lock:
                            self.downloaded += 1
                    self._persist_counters()
                    self._emit_progress("running")
        self._check_cancel()

    def _download_one(self, http: httpx.Client, task: dict) -> bool:
        self._check_cancel()
        item: ig.PostItem = task["item"]
        info: ig.PostInfo = task["info"]
        target = self._target_path(info, item)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + ".part")

        last_exc: Optional[Exception] = None
        for attempt in range(3):
            if attempt:
                time.sleep(2 * 3 ** (attempt - 1))  # 2s, 6s
            try:
                with http.stream("GET", item.url) as resp:
                    resp.raise_for_status()
                    with open(tmp, "wb") as fh:
                        for chunk in resp.iter_bytes(65536):
                            if self._cancel.is_set():
                                raise Cancelled()
                            fh.write(chunk)
                os.replace(tmp, target)
                break
            except Cancelled:
                tmp.unlink(missing_ok=True)
                raise
            except Exception as exc:
                tmp.unlink(missing_ok=True)
                last_exc = exc
        else:
            self._record_failure(task, last_exc or RuntimeError("download failed"))
            return False

        # Metadata first (embedding rewrites the file), then the mtime.
        self._save_metadata(target, info, item)
        if info.taken_at is not None:
            ts = info.taken_at.replace(tzinfo=timezone.utc).timestamp()
            os.utime(target, (ts, ts))
        self._record_media(target, info, item)
        return True

    def _record_failure(self, task: dict, exc: BaseException) -> None:
        item: ig.PostItem = task["item"]
        info: ig.PostInfo = task["info"]
        status = None
        if isinstance(exc, httpx.HTTPStatusError):
            status = exc.response.status_code
        write_failure_detail(
            self._err,
            job_id=self.job_id,
            context=f"download shortcode={info.shortcode} child={item.index} type={item.media_type}",
            exc=exc,
            url=item.url,
            http_status=status,
        )
        self._log.error("Download failed: %s #%d (%s)",
                        info.shortcode, item.index, type(exc).__name__)
        with self._counter_lock:
            self.failed += 1
        self._set_link(task["link"].id, error=summarise_error(exc))

    # ---- files -----------------------------------------------------------

    def _target_path(self, info: ig.PostInfo, item: ig.PostItem) -> Path:
        username = info.username or "unknown"
        date = info.taken_at.strftime("%Y%m%d") if info.taken_at else "00000000"
        ext = Path(urlparse(item.url).path).suffix.lower()
        if ext not in _IMAGE_EXTS | _VIDEO_EXTS:
            ext = ".mp4" if item.media_type == "video" else ".jpg"
        suffix = f"_{item.index:02d}" if item.index else ""
        return config.DOWNLOAD_DIR / username / f"{date}_{info.shortcode}{suffix}{ext}"

    def _save_metadata(self, target: Path, info: ig.PostInfo, item: ig.PostItem) -> None:
        """Embed metadata into JPEGs (lossless EXIF splice); fall back to a
        .json sidecar for videos and non-JPEG files."""
        if target.suffix.lower() in (".jpg", ".jpeg"):
            try:
                embed_exif(target, info, item)
                return
            except Exception as exc:
                self._log.warning(
                    "Could not embed EXIF in %s (%s); writing sidecar instead",
                    target.name, exc,
                )
        self._write_sidecar(target, info, item)

    def _write_sidecar(self, target: Path, info: ig.PostInfo, item: ig.PostItem) -> None:
        import json

        try:
            with open(str(target) + ".json", "w", encoding="utf-8") as fh:
                json.dump(metadata_payload(info, item), fh, ensure_ascii=False, indent=2)
        except OSError as exc:
            self._log.warning("Could not write sidecar for %s: %s", target.name, exc)

    # ---- persistence / events --------------------------------------------

    def _load_links(self) -> list[Link]:
        from sqlmodel import select

        with session_scope() as session:
            rows = session.exec(
                select(Link).where(Link.job_id == self.job_id).order_by(Link.id)
            ).all()
            for row in rows:
                session.expunge(row)
            return list(rows)

    def _record_media(self, target: Path, info: ig.PostInfo, item: ig.PostItem) -> None:
        with session_scope() as session:
            session.add(Media(
                job_id=self.job_id,
                shortcode=info.shortcode,
                child_index=item.index,
                media_type=item.media_type,
                username=info.username,
                file_path=str(target),
                width=item.width,
                height=item.height,
                taken_at=info.taken_at,
                caption=(info.caption or "")[:500] or None,
            ))

    def _mark_links_done(self) -> None:
        """Links whose fetch succeeded end 'done' unless they saw a failure."""
        from sqlmodel import select

        with session_scope() as session:
            rows = session.exec(select(Link).where(Link.job_id == self.job_id)).all()
            for row in rows:
                if row.status == "fetching":
                    row.status = "done" if not row.error else "failed"
                    session.add(row)
                elif row.status == "pending":
                    row.status = "skipped"
                    row.error = row.error or "Job ended before this link was fetched."
                    session.add(row)

    def _set_link(self, link_id: int, **fields) -> None:
        with session_scope() as session:
            row = session.get(Link, link_id)
            if row is None:
                return
            for key, value in fields.items():
                setattr(row, key, value)
            session.add(row)
            session.flush()
            payload = {
                "id": row.id, "url": row.url, "shortcode": row.shortcode,
                "status": row.status, "username": row.username,
                "media_count": row.media_count, "error": row.error,
            }
        broker.publish(self.job_id, {"type": "link", "link": payload})

    def _update_job(self, **fields) -> None:
        with session_scope() as session:
            job = session.get(Job, self.job_id)
            if job is None:
                return
            for key, value in fields.items():
                setattr(job, key, value)
            session.add(job)

    def _persist_counters(self) -> None:
        self._update_job(
            total=self.total, downloaded=self.downloaded,
            skipped=self.skipped, failed=self.failed,
        )

    def _emit_progress(self, status: str, error: Optional[str] = None) -> None:
        event = {
            "type": "progress", "status": status, "total": self.total,
            "downloaded": self.downloaded, "skipped": self.skipped,
            "failed": self.failed,
        }
        if error:
            event["error"] = error
        broker.publish(self.job_id, event)

    def _finish(self, status: str, error: Optional[str] = None) -> None:
        self._persist_counters()
        self._update_job(status=status, finished_at=utcnow(), error=error)
        event_status = status
        self._log.info("Job finished: %s (%d downloaded, %d skipped, %d failed)",
                       status, self.downloaded, self.skipped, self.failed)
        broker.publish(self.job_id, {
            "type": "done", "status": event_status, "total": self.total,
            "downloaded": self.downloaded, "skipped": self.skipped,
            "failed": self.failed, "error": error,
        })

    # ---- misc ------------------------------------------------------------

    def _sleep_rate_limit(self) -> None:
        hi = self.settings.rate_limit_max
        lo = self.settings.rate_limit_min
        if hi > 0:
            delay = random.uniform(lo, hi)
            for _ in range(int(delay * 10)):
                if self._cancel.is_set():
                    raise Cancelled()
                time.sleep(0.1)

    def _check_cancel(self) -> None:
        if self._cancel.is_set():
            raise Cancelled()
