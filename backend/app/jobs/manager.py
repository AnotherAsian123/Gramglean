"""Job orchestration: a bounded thread pool runs ScrapeRunner instances."""
from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Dict

from sqlmodel import select

from ..core import config
from ..core.settings_service import get_effective
from ..db.database import session_scope
from ..db.models import Account, Job
from .scraper import ScrapeRunner

log = logging.getLogger(__name__)


class JobManager:
    def __init__(self) -> None:
        self._executor = ThreadPoolExecutor(
            max_workers=config.MAX_CONCURRENT_JOBS, thread_name_prefix="scrape"
        )
        self._cancel_events: Dict[int, threading.Event] = {}
        self._lock = threading.Lock()

    def start(self) -> None:
        """On boot: fail jobs that were interrupted, requeue pending ones."""
        with session_scope() as session:
            running = session.exec(select(Job).where(Job.status == "running")).all()
            for job in running:
                job.status = "failed"
                job.error = "Interrupted by restart."
                job.finished_at = datetime.utcnow()
                session.add(job)
            queued = session.exec(select(Job).where(Job.status == "queued")).all()
            queued_ids = [j.id for j in queued]
        for job_id in queued_ids:
            self._dispatch(job_id)

    def submit(self, job_id: int) -> None:
        self._dispatch(job_id)

    def cancel(self, job_id: int) -> bool:
        with self._lock:
            event = self._cancel_events.get(job_id)
        if event:
            event.set()
            return True
        # Not running yet: cancel it directly if still queued.
        with session_scope() as session:
            job = session.get(Job, job_id)
            if job and job.status == "queued":
                job.status = "cancelled"
                job.finished_at = datetime.utcnow()
                session.add(job)
                return True
        return False

    def _dispatch(self, job_id: int) -> None:
        event = threading.Event()
        with self._lock:
            self._cancel_events[job_id] = event
        self._executor.submit(self._run, job_id, event)

    def _run(self, job_id: int, cancel_event: threading.Event) -> None:
        try:
            with session_scope() as session:
                job = session.get(Job, job_id)
                if job is None or job.status not in ("queued",):
                    return
                account = session.get(Account, job.account_id)
                if account is None:
                    job.status = "failed"
                    job.error = "Account no longer exists."
                    session.add(job)
                    return
                settings = get_effective(session)
                runner_args = dict(
                    job_id=job.id,
                    account_id=account.id,
                    username=account.username,
                    include_posts=job.include_posts,
                    include_reels=job.include_reels,
                    include_stories=job.include_stories,
                )
            runner = ScrapeRunner(settings=settings, cancel_event=cancel_event, **runner_args)
            runner.run()
        except Exception:  # noqa: BLE001 - never let a worker thread die silently
            log.exception("Job %s crashed", job_id)
            with session_scope() as session:
                job = session.get(Job, job_id)
                if job and job.status in ("queued", "running"):
                    job.status = "failed"
                    job.error = "Internal error; see container logs."
                    job.finished_at = datetime.utcnow()
                    session.add(job)
        finally:
            with self._lock:
                self._cancel_events.pop(job_id, None)

    def shutdown(self) -> None:
        for event in list(self._cancel_events.values()):
            event.set()
        self._executor.shutdown(wait=False, cancel_futures=True)


manager = JobManager()
