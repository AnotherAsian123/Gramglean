"""Logging: stdout (docker logs) + rotating files under CONFIG_DIR/logs.

Files:
  gramglean.log         general application log (rotating, 5 MB x 3)
  failed_downloads.log  one detailed block per failed resource, all jobs (rotating)
  job-<id>.log          per-job activity (pruned after LOG_RETENTION_DAYS)
  job-<id>.errors.log   per-job failures only (pruned after LOG_RETENTION_DAYS)
"""
from __future__ import annotations

import logging
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

from ..core import config

_FMT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
_MARK = "_gramglean"


def setup_logging() -> None:
    root = logging.getLogger()
    root.setLevel(config.LOG_LEVEL if config.LOG_LEVEL in ("DEBUG", "INFO") else "INFO")
    if any(getattr(h, _MARK, False) for h in root.handlers):
        return

    formatter = logging.Formatter(_FMT)

    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    setattr(stream, _MARK, True)
    root.addHandler(stream)

    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    app_file = RotatingFileHandler(
        config.LOGS_DIR / "gramglean.log", maxBytes=5 * 1024 * 1024, backupCount=3
    )
    app_file.setFormatter(formatter)
    setattr(app_file, _MARK, True)
    root.addHandler(app_file)

    for noisy in ("httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def failed_downloads_handler() -> RotatingFileHandler:
    """Shared, rotating detail log for every failed resource across all jobs."""
    handler = RotatingFileHandler(
        config.LOGS_DIR / "failed_downloads.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=2,
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    return handler


def job_log_path(job_id: int) -> Path:
    return config.LOGS_DIR / f"job-{job_id}.log"


def job_error_log_path(job_id: int) -> Path:
    return config.LOGS_DIR / f"job-{job_id}.errors.log"


def prune_old_job_logs() -> int:
    """Delete job-*.log files older than LOG_RETENTION_DAYS. Runs at startup."""
    cutoff = time.time() - config.LOG_RETENTION_DAYS * 86400
    removed = 0
    for path in config.LOGS_DIR.glob("job-*.log"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
                removed += 1
        except OSError:
            pass
    if removed:
        logging.getLogger(__name__).info("Pruned %d old job log(s)", removed)
    return removed
