"""Job dispatch: a small thread pool plus cancellation events.

Cancelling a queued job flips its DB status immediately, so a job that has
not started yet never runs (the worker re-checks status before starting).
"""
from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Dict

from ..core import config
from ..core.settings_service import get_effective
from ..db.database import session_scope
from ..db.models import Job, utcnow
from .runner import JobRunner

log = logging.getLogger(__name__)


class JobManager:
    def __init__(self) -> None:
        self._pool = ThreadPoolExecutor(
            max_workers=config.MAX_CONCURRENT_JOBS, thread_name_prefix="job"
        )
        self._cancel_events: Dict[int, threading.Event] = {}
        self._lock = threading.Lock()

    def submit(self, job_id: int) -> None:
        event = threading.Event()
        with self._lock:
            self._cancel_events[job_id] = event
        self._pool.submit(self._run, job_id, event)

    def cancel(self, job_id: int) -> bool:
        with self._lock:
            event = self._cancel_events.get(job_id)
        with session_scope() as session:
            job = session.get(Job, job_id)
            if job is None or job.status not in ("queued", "running"):
                return False
            if job.status == "queued":
                job.status = "cancelled"
                job.finished_at = utcnow()
                session.add(job)
        if event is not None:
            event.set()
        return True

    def _run(self, job_id: int, cancel: threading.Event) -> None:
        try:
            with session_scope() as session:
                job = session.get(Job, job_id)
                if job is None or job.status != "queued":
                    return
                settings = get_effective(session)
            JobRunner(job_id, settings, cancel).run()
        except Exception:
            log.exception("Unhandled error running job %d", job_id)
            with session_scope() as session:
                job = session.get(Job, job_id)
                if job is not None and job.status in ("queued", "running"):
                    job.status = "failed"
                    job.finished_at = utcnow()
                    job.error = ("An internal error occurred. "
                                 "See the log file for full details.")
                    session.add(job)
        finally:
            with self._lock:
                self._cancel_events.pop(job_id, None)

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)


manager = JobManager()
