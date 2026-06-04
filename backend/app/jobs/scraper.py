"""The scrape engine.

Flow for one job:
  1. Pick a cookie file and build an authenticated instaloader context.
  2. Enumerate the account's posts (incl. carousel children) and reels, plus
     stories if requested, collecting full-resolution media URLs + metadata.
     Already-archived resources are skipped (incremental sync); once a fully
     archived post is reached, pagination stops early.
  3. Download every new resource in parallel with a thread pool (IO-bound work),
     set each file's mtime to the original post date, and write a JSON metadata
     sidecar.
  4. Every failed resource is written, one per line, to the job's error log.

On a rate limit / lock during enumeration the cookie is rotated and enumeration
restarts with the next available cookie.
"""
from __future__ import annotations

import json
import logging
import os
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, List, Optional, Set, Tuple
from urllib.parse import urlparse

import httpx
import instaloader
from instaloader.exceptions import (
    ConnectionException,
    InstaloaderException,
    LoginRequiredException,
    PrivateProfileNotFollowedException,
    ProfileNotExistsException,
    TooManyRequestsException,
)
from sqlmodel import select

from ..core import config
from ..core.logging_setup import (
    job_error_log_path,
    job_log_path,
    shared_error_log_path,
)
from ..core.settings_service import EffectiveSettings
from ..db.database import session_scope
from ..db.models import Account, Job, Media
from . import cookies as cookie_mgr
from .broker import broker

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".gif"}
_VIDEO_EXTS = {".mp4", ".mov", ".webm"}


# --- control-flow exceptions -------------------------------------------------
class RateLimited(Exception):
    pass


class CookieInvalid(Exception):
    pass


class ProfileNotFound(Exception):
    pass


@dataclass
class DownloadItem:
    shortcode: str
    child_index: int
    is_video: bool
    url: str
    source: str          # post | carousel | reel | story
    taken_at: Optional[datetime]
    caption: Optional[str]

    @property
    def media_type(self) -> str:
        return "video" if self.is_video else "image"


class ScrapeRunner:
    def __init__(
        self,
        job_id: int,
        account_id: int,
        username: str,
        include_posts: bool,
        include_reels: bool,
        include_stories: bool,
        settings: EffectiveSettings,
        cancel_event: threading.Event,
    ) -> None:
        self.job_id = job_id
        self.account_id = account_id
        self.username = username
        self.include_posts = include_posts
        self.include_reels = include_reels
        self.include_stories = include_stories
        self.settings = settings
        self._cancel = cancel_event

        self.downloaded = 0
        self.skipped = 0
        self.failed = 0
        self.total = 0
        self.status = "running"

        self.existing: Set[Tuple[str, int]] = set()
        self._client: Optional[httpx.Client] = None
        self._log = logging.getLogger(f"job.{job_id}")
        self._errlog = logging.getLogger(f"job.{job_id}.errors")
        self._counter_lock = threading.Lock()

    # ------------------------------------------------------------------ logging
    def _setup_loggers(self) -> Tuple[str, str]:
        log_path = job_log_path(self.job_id)
        err_path = job_error_log_path(self.job_id)

        self._log.setLevel(logging.INFO)
        self._log.propagate = False
        fh = logging.FileHandler(log_path, encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s"))
        self._log.addHandler(fh)

        # One clean line per failed resource, to both the per-job and shared file.
        self._errlog.setLevel(logging.ERROR)
        self._errlog.propagate = False
        for path in (err_path, shared_error_log_path()):
            eh = logging.FileHandler(path, encoding="utf-8")
            eh.setFormatter(logging.Formatter("%(message)s"))
            self._errlog.addHandler(eh)

        return str(log_path), str(err_path)

    def _teardown_loggers(self) -> None:
        for logger in (self._log, self._errlog):
            for handler in list(logger.handlers):
                handler.close()
                logger.removeHandler(handler)

    def _info(self, message: str) -> None:
        self._log.info(message)
        self._emit(type="log", level="info", message=message)

    def _emit(self, **event) -> None:
        event.setdefault("job_id", self.job_id)
        broker.publish(self.job_id, event)

    def _emit_progress(self) -> None:
        self._emit(
            type="progress",
            status=self.status,
            total=self.total,
            downloaded=self.downloaded,
            skipped=self.skipped,
            failed=self.failed,
        )

    # ------------------------------------------------------------------- public
    def run(self) -> None:
        log_path, err_path = self._setup_loggers()
        with session_scope() as session:
            job = session.get(Job, self.job_id)
            if job:
                job.status = "running"
                job.started_at = datetime.utcnow()
                job.log_path = log_path
                job.error_log_path = err_path
                session.add(job)
        self._info(
            f"Starting scrape of @{self.username} "
            f"(posts={self.include_posts}, reels={self.include_reels}, "
            f"stories={self.include_stories}, threads={self.settings.download_threads})"
        )
        self._load_existing()
        self._emit_progress()

        try:
            items = self._enumerate_with_rotation()
        except ProfileNotFound as exc:
            return self._finish(
                "failed", error=str(exc) or f"Profile @{self.username} not found."
            )
        except CookieInvalid:
            return self._finish(
                "failed",
                error="No valid cookies. Upload a fresh Instagram cookies.txt in Settings.",
            )
        except RateLimited:
            return self._finish(
                "rate_limited",
                error="Instagram rate-limited every available cookie. Wait, or add more cookies.",
            )
        except Exception as exc:  # noqa: BLE001 - surface anything unexpected
            self._log.exception("Enumeration failed")
            return self._finish("failed", error=f"Enumeration error: {exc}")

        if self._cancel.is_set():
            return self._finish("cancelled")

        self.total = len(items)
        self._info(
            f"Discovered {self.total} new resource(s) to download "
            f"({self.skipped} already archived)."
        )
        self._emit_progress()

        if items:
            self._download_all(items)

        if self._cancel.is_set():
            return self._finish("cancelled")
        self._mark_account_synced()
        self._finish("completed")

    # --------------------------------------------------------------- internals
    def _load_existing(self) -> None:
        with session_scope() as session:
            rows = session.exec(
                select(Media.shortcode, Media.child_index).where(
                    Media.account_id == self.account_id
                )
            ).all()
        self.existing = {(sc, ci) for sc, ci in rows}

    def _build_loader(self, cookie_file_path: Path) -> instaloader.Instaloader:
        from http.cookiejar import MozillaCookieJar

        loader = instaloader.Instaloader(
            quiet=True,
            download_videos=True,
            save_metadata=False,
            download_comments=False,
            download_geotags=False,
            max_connection_attempts=2,
            request_timeout=config.REQUEST_TIMEOUT,
            user_agent=config.USER_AGENT,
        )
        jar = MozillaCookieJar(str(cookie_file_path))
        jar.load(ignore_discard=True, ignore_expires=True)
        loader.context._session.cookies.update(jar)
        try:
            username = loader.test_login()
        except InstaloaderException as exc:
            raise CookieInvalid(str(exc)) from exc
        if not username:
            raise CookieInvalid("cookies did not authenticate")
        loader.context.username = username
        return loader

    def _enumerate_with_rotation(self) -> List[DownloadItem]:
        tried: Set[int] = set()
        last_error: Optional[Exception] = None
        while True:
            cookie = cookie_mgr.next_cookie(exclude_ids=tried)
            if cookie is None:
                if last_error is None:
                    raise CookieInvalid("no cookies uploaded")
                raise (last_error if isinstance(last_error, (RateLimited,)) else last_error)
            tried.add(cookie.id)  # type: ignore[arg-type]
            cookie_mgr.mark_used(cookie.id)  # type: ignore[arg-type]
            self._record_cookie(cookie.label or cookie.original_name or cookie.filename)
            try:
                loader = self._build_loader(cookie_mgr.cookie_path(cookie))
            except CookieInvalid as exc:
                cookie_mgr.mark_status(cookie.id, "invalid", str(exc))  # type: ignore[arg-type]
                self._info(f"Cookie '{cookie.original_name}' invalid; trying next.")
                last_error = exc
                continue
            try:
                items = self._enumerate(loader)
                cookie_mgr.mark_status(cookie.id, "ok")  # type: ignore[arg-type]
                return items
            except RateLimited as exc:
                cookie_mgr.mark_status(cookie.id, "rate_limited", str(exc))  # type: ignore[arg-type]
                self._info(f"Cookie '{cookie.original_name}' rate-limited; rotating.")
                last_error = exc
                continue
            except CookieInvalid as exc:
                cookie_mgr.mark_status(cookie.id, "invalid", str(exc))  # type: ignore[arg-type]
                last_error = exc
                continue

    def _enumerate(self, loader: instaloader.Instaloader) -> List[DownloadItem]:
        items: List[DownloadItem] = []
        try:
            profile = instaloader.Profile.from_username(loader.context, self.username)
            self._update_account_meta(profile)

            if self.include_posts or self.include_reels:
                for post in profile.get_posts():
                    if self._cancel.is_set():
                        break
                    wanted = [it for it in self._items_for_post(post) if self._wanted(it)]
                    if wanted and all(
                        (it.shortcode, it.child_index) in self.existing for it in wanted
                    ):
                        # Reached already-archived history; older posts are known.
                        self.skipped += len(wanted)
                        self._info("Reached already-archived posts; stopping early.")
                        break
                    for it in wanted:
                        if (it.shortcode, it.child_index) in self.existing:
                            self.skipped += 1
                        else:
                            items.append(it)
                    self._sleep()

            if self.include_stories and not self._cancel.is_set():
                items.extend(self._enumerate_stories(loader, profile))

            return items
        except TooManyRequestsException as exc:
            raise RateLimited(str(exc)) from exc
        except LoginRequiredException as exc:
            raise CookieInvalid(str(exc)) from exc
        except PrivateProfileNotFollowedException as exc:
            raise ProfileNotFound(
                f"@{self.username} is private and the cookie's account does not follow it."
            ) from exc
        except ProfileNotExistsException as exc:
            raise ProfileNotFound(str(exc)) from exc
        except ConnectionException as exc:
            msg = str(exc).lower()
            if any(k in msg for k in ("401", "login_required", "checkpoint", "challenge")):
                raise CookieInvalid(str(exc)) from exc
            if any(k in msg for k in ("429", "rate", "wait a few minutes", "please wait")):
                raise RateLimited(str(exc)) from exc
            raise

    def _enumerate_stories(self, loader, profile) -> List[DownloadItem]:
        out: List[DownloadItem] = []
        try:
            for story in loader.get_stories(userids=[profile.userid]):
                for item in story.get_items():
                    if self._cancel.is_set():
                        return out
                    shortcode = getattr(item, "shortcode", None) or str(item.mediaid)
                    di = DownloadItem(
                        shortcode=shortcode,
                        child_index=0,
                        is_video=item.is_video,
                        url=item.video_url if item.is_video else item.url,
                        source="story",
                        taken_at=item.date_utc,
                        caption=None,
                    )
                    if not self._wanted(di):
                        continue
                    if (di.shortcode, di.child_index) in self.existing:
                        self.skipped += 1
                    else:
                        out.append(di)
                self._sleep()
        except TooManyRequestsException as exc:
            raise RateLimited(str(exc)) from exc
        return out

    def _items_for_post(self, post) -> List[DownloadItem]:
        taken = post.date_utc
        caption = post.caption
        if post.typename == "GraphSidecar":
            result: List[DownloadItem] = []
            for index, node in enumerate(post.get_sidecar_nodes()):
                result.append(
                    DownloadItem(
                        shortcode=post.shortcode,
                        child_index=index,
                        is_video=node.is_video,
                        url=node.video_url if node.is_video else node.display_url,
                        source="carousel",
                        taken_at=taken,
                        caption=caption,
                    )
                )
            return result
        is_video = post.is_video
        return [
            DownloadItem(
                shortcode=post.shortcode,
                child_index=0,
                is_video=is_video,
                url=post.video_url if is_video else post.url,
                source="reel" if is_video else "post",
                taken_at=taken,
                caption=caption,
            )
        ]

    def _wanted(self, item: DownloadItem) -> bool:
        if item.source == "story":
            return self.include_stories
        if item.is_video:
            return self.include_reels
        return self.include_posts

    def _sleep(self) -> None:
        lo, hi = self.settings.rate_limit_min, self.settings.rate_limit_max
        if hi > 0:
            time.sleep(random.uniform(lo, hi))

    # ------------------------------------------------------------- downloading
    def _download_all(self, items: List[DownloadItem]) -> None:
        headers = {
            "User-Agent": config.USER_AGENT,
            "Referer": "https://www.instagram.com/",
        }
        with httpx.Client(
            headers=headers,
            timeout=config.REQUEST_TIMEOUT,
            follow_redirects=True,
        ) as client:
            self._client = client
            with ThreadPoolExecutor(max_workers=self.settings.download_threads) as ex:
                futures = [ex.submit(self._download_one, it) for it in items]
                for fut in as_completed(futures):
                    self._handle_result(fut.result())

    def _download_one(self, item: DownloadItem) -> dict:
        if self._cancel.is_set():
            return {"status": "cancelled", "item": item}
        target = self._target_path(item)
        tmp = target.with_name(target.name + ".part")
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            assert self._client is not None
            with self._client.stream("GET", item.url) as resp:
                resp.raise_for_status()
                with open(tmp, "wb") as fh:
                    for chunk in resp.iter_bytes(65536):
                        if self._cancel.is_set():
                            raise RuntimeError("cancelled")
                        fh.write(chunk)
            os.replace(tmp, target)
            if item.taken_at:
                # instaloader's *_utc datetimes are naive UTC; pin the tz so the
                # file mtime reflects the true original post time.
                aware = item.taken_at.replace(tzinfo=timezone.utc)
                ts = aware.timestamp()
                os.utime(target, (ts, ts))
            self._write_sidecar(item, target)
            return {"status": "ok", "item": item, "path": str(target)}
        except Exception as exc:  # noqa: BLE001 - per-resource failures are expected
            tmp.unlink(missing_ok=True)
            http_status = None
            response = getattr(exc, "response", None)
            if response is not None:
                http_status = getattr(response, "status_code", None)
            return {"status": "failed", "item": item, "error": exc, "http_status": http_status}

    def _handle_result(self, res: dict) -> None:
        status = res["status"]
        item: DownloadItem = res["item"]
        if status == "ok":
            self._record_media(item, res["path"])
            with self._counter_lock:
                self.downloaded += 1
        elif status == "failed":
            with self._counter_lock:
                self.failed += 1
            self._log_failure(item, res["error"], res.get("http_status"))
        else:  # cancelled
            return
        self._persist_counters()
        self._emit_progress()

    def _target_path(self, item: DownloadItem) -> Path:
        date = item.taken_at.strftime("%Y%m%d") if item.taken_at else "nodate"
        ext = self._extension_for(item)
        suffix = f"_{item.child_index}" if item.source == "carousel" else ""
        name = f"{date}_{item.shortcode}{suffix}{ext}"
        return config.DOWNLOAD_DIR / self.username / item.source / name

    @staticmethod
    def _extension_for(item: DownloadItem) -> str:
        ext = os.path.splitext(urlparse(item.url).path)[1].lower()
        if item.is_video and ext in _VIDEO_EXTS:
            return ext
        if not item.is_video and ext in _IMAGE_EXTS:
            return ext
        return ".mp4" if item.is_video else ".jpg"

    def _write_sidecar(self, item: DownloadItem, target: Path) -> None:
        meta = {
            "username": self.username,
            "shortcode": item.shortcode,
            "child_index": item.child_index,
            "source": item.source,
            "media_type": item.media_type,
            "taken_at": item.taken_at.isoformat() if item.taken_at else None,
            "caption": item.caption,
            "source_url": item.url,
            "downloaded_at": datetime.utcnow().isoformat() + "Z",
        }
        with open(str(target) + ".json", "w", encoding="utf-8") as fh:
            json.dump(meta, fh, ensure_ascii=False, indent=2)

    def _log_failure(self, item: DownloadItem, error: Exception, http_status) -> None:
        message = str(error).replace("\n", " ").replace("\t", " ").strip()
        line = (
            f"{datetime.utcnow().isoformat()}Z"
            f"\tuser=@{self.username}"
            f"\tsource={item.source}"
            f"\tshortcode={item.shortcode}"
            f"\tchild={item.child_index}"
            f"\ttype={item.media_type}"
            f"\thttp={http_status}"
            f"\terror={type(error).__name__}: {message}"
            f"\turl={item.url}"
        )
        self._errlog.error(line)

    # ------------------------------------------------------------------- db ops
    def _record_media(self, item: DownloadItem, path: str) -> None:
        with session_scope() as session:
            session.add(
                Media(
                    account_id=self.account_id,
                    job_id=self.job_id,
                    shortcode=item.shortcode,
                    child_index=item.child_index,
                    media_type=item.media_type,
                    source=item.source,
                    file_path=path,
                    taken_at=item.taken_at,
                    caption=item.caption,
                )
            )
        self.existing.add((item.shortcode, item.child_index))

    def _persist_counters(self) -> None:
        with session_scope() as session:
            job = session.get(Job, self.job_id)
            if job:
                job.total = self.total
                job.downloaded = self.downloaded
                job.skipped = self.skipped
                job.failed = self.failed
                session.add(job)

    def _record_cookie(self, label: str) -> None:
        with session_scope() as session:
            job = session.get(Job, self.job_id)
            if job:
                job.cookie_used = label
                session.add(job)

    def _update_account_meta(self, profile) -> None:
        with session_scope() as session:
            account = session.get(Account, self.account_id)
            if account:
                account.full_name = profile.full_name
                account.profile_pic_url = profile.profile_pic_url
                account.instagram_userid = str(profile.userid)
                session.add(account)

    def _mark_account_synced(self) -> None:
        with session_scope() as session:
            account = session.get(Account, self.account_id)
            if account:
                account.last_synced_at = datetime.utcnow()
                session.add(account)

    def _finish(self, status: str, error: Optional[str] = None) -> None:
        self.status = status
        with session_scope() as session:
            job = session.get(Job, self.job_id)
            if job:
                job.status = status
                job.finished_at = datetime.utcnow()
                job.total = self.total
                job.downloaded = self.downloaded
                job.skipped = self.skipped
                job.failed = self.failed
                job.error = error
                session.add(job)
        summary = (
            f"Job {status}: downloaded={self.downloaded}, skipped={self.skipped}, "
            f"failed={self.failed}, total={self.total}"
        )
        if error:
            summary += f" | {error}"
        self._log.info(summary)
        self._emit(
            type="done",
            status=status,
            total=self.total,
            downloaded=self.downloaded,
            skipped=self.skipped,
            failed=self.failed,
            error=error,
        )
        self._teardown_loggers()
