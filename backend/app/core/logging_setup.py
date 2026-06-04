"""Logging configuration.

Three logging surfaces:
  * the root/app logger -> stdout (visible in `docker logs`) + /config/logs/app.log
  * a per-job activity log -> /config/logs/job-<id>.log
  * a per-resource failure log -> /config/logs/job-<id>.errors.log and a shared
    /config/logs/errors.log, with exactly one line per failed resource so you can
    review afterwards why each picture/reel/story failed.
"""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from . import config

_FMT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"


def setup_logging() -> None:
    config.ensure_dirs()
    root = logging.getLogger()
    root.setLevel(config.LOG_LEVEL)

    # Avoid duplicate handlers if called twice (e.g. reload).
    if any(getattr(h, "_unraiders", False) for h in root.handlers):
        return

    stream = logging.StreamHandler()
    stream.setFormatter(logging.Formatter(_FMT))
    stream._unraiders = True  # type: ignore[attr-defined]
    root.addHandler(stream)

    app_file = RotatingFileHandler(
        config.LOGS_DIR / "app.log", maxBytes=5_000_000, backupCount=3, encoding="utf-8"
    )
    app_file.setFormatter(logging.Formatter(_FMT))
    app_file._unraiders = True  # type: ignore[attr-defined]
    root.addHandler(app_file)

    # instaloader is chatty at INFO; keep it at WARNING unless we're debugging.
    if config.LOG_LEVEL != "DEBUG":
        logging.getLogger("instaloader").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def job_log_path(job_id: int) -> Path:
    return config.LOGS_DIR / f"job-{job_id}.log"


def job_error_log_path(job_id: int) -> Path:
    return config.LOGS_DIR / f"job-{job_id}.errors.log"


def shared_error_log_path() -> Path:
    return config.LOGS_DIR / "errors.log"
