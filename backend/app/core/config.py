"""Runtime configuration.

Values come from environment variables (set when creating the Unraid container)
with sensible, safety-first defaults. A few of these (rate limits, thread count,
default content toggles) can also be overridden at runtime from the Settings UI;
see ``settings_service`` for how the effective values are resolved.
"""
from __future__ import annotations

import os
from pathlib import Path


def _int(name: str, default: int, minimum: int = 1) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


def _float(name: str, default: float, minimum: float = 0.0) -> float:
    try:
        return max(minimum, float(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


# --- Paths (mapped as Unraid volumes) ---------------------------------------
CONFIG_DIR = Path(os.getenv("CONFIG_DIR", "/config"))
DOWNLOAD_DIR = Path(os.getenv("DOWNLOAD_DIR", "/downloads"))
COOKIES_DIR = CONFIG_DIR / "cookies"
LOGS_DIR = CONFIG_DIR / "logs"
DB_PATH = CONFIG_DIR / "app.db"

# --- Server -----------------------------------------------------------------
PORT = _int("PORT", 8080)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# --- Concurrency ------------------------------------------------------------
# Number of worker threads used to download individual media files in parallel.
# Downloading is network/IO-bound, so threads (which release the GIL during IO)
# are both faster and lighter than separate processes here. Higher values are
# faster but increase the chance of tripping Instagram's rate limits / locks.
DOWNLOAD_THREADS = _int("DOWNLOAD_THREADS", 4)

# How many scrape jobs may run at the same time. Kept at 1 by default: running
# multiple account scrapes in parallel is the fastest way to get an account
# flagged. Raise only if you understand the ban risk.
MAX_CONCURRENT_JOBS = _int("MAX_CONCURRENT_JOBS", 1)

# --- Rate limiting (defaults; overridable from the Settings UI) -------------
# A randomized delay (uniform between MIN and MAX seconds) is inserted between
# Instagram API page requests during enumeration to look more human.
RATE_LIMIT_MIN = _float("RATE_LIMIT_MIN", 2.0)
RATE_LIMIT_MAX = _float("RATE_LIMIT_MAX", 5.0)

# --- Networking -------------------------------------------------------------
USER_AGENT = os.getenv(
    "USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
)
REQUEST_TIMEOUT = _float("REQUEST_TIMEOUT", 120.0, minimum=10.0)


def ensure_dirs() -> None:
    """Create the directory layout under the mapped volumes if missing."""
    for d in (CONFIG_DIR, DOWNLOAD_DIR, COOKIES_DIR, LOGS_DIR):
        d.mkdir(parents=True, exist_ok=True)
