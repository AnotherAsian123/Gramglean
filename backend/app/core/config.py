"""Environment-driven configuration.

Every tunable has a sane default for the Unraid container; nothing here is
required to boot a dev instance (CONFIG_DIR / DOWNLOAD_DIR default to /config
and /downloads which the entrypoint creates).
"""
from __future__ import annotations

import os
from pathlib import Path


def _int(name: str, default: int, minimum: int = 1) -> int:
    try:
        return max(minimum, int(os.getenv(name, default)))
    except (TypeError, ValueError):
        return default


def _float(name: str, default: float, minimum: float = 0.0) -> float:
    try:
        return max(minimum, float(os.getenv(name, default)))
    except (TypeError, ValueError):
        return default


CONFIG_DIR = Path(os.getenv("CONFIG_DIR", "/config"))
DOWNLOAD_DIR = Path(os.getenv("DOWNLOAD_DIR", "/downloads"))
STATIC_DIR = Path(os.getenv("STATIC_DIR", "/app/static"))

COOKIES_DIR = CONFIG_DIR / "cookies"
LOGS_DIR = CONFIG_DIR / "logs"
DB_PATH = CONFIG_DIR / "gramglean.db"

PORT = _int("PORT", 8080)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

DOWNLOAD_THREADS = _int("DOWNLOAD_THREADS", 4)
MAX_CONCURRENT_JOBS = _int("MAX_CONCURRENT_JOBS", 1)
RATE_LIMIT_MIN = _float("RATE_LIMIT_MIN", 2.0)
RATE_LIMIT_MAX = _float("RATE_LIMIT_MAX", 5.0)

REQUEST_TIMEOUT = _float("REQUEST_TIMEOUT", 60.0, minimum=10.0)

# Days to keep per-job log files. Old job-*.log files are pruned at startup so
# /config/logs cannot grow unbounded on a long-lived Unraid install.
LOG_RETENTION_DAYS = _int("LOG_RETENTION_DAYS", 30)

# Allow the Vite dev server origin to call the API. Off in production because
# the SPA is served same-origin by FastAPI.
DEV_CORS = os.getenv("DEV_CORS", "").lower() in ("1", "true", "yes")

USER_AGENT = os.getenv(
    "USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
)

# Instagram web-app id: sent as x-ig-app-id on API requests, same as the
# browser client does. Public constant, not a secret.
IG_APP_ID = "936619743392459"


def ensure_dirs() -> None:
    for path in (CONFIG_DIR, COOKIES_DIR, LOGS_DIR, DOWNLOAD_DIR):
        path.mkdir(parents=True, exist_ok=True)
