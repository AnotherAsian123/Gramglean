"""The two halves of every failure, produced together at the point of failure.

summarise_error()      -> short, friendly, actionable line for the UI.
write_failure_detail() -> full context (traceback, URL, HTTP status) to the
                          per-job errors log AND the shared rotating
                          failed_downloads.log.
"""
from __future__ import annotations

import logging
import traceback
from datetime import datetime, timezone

import httpx

from ..insta.client import FetchError, LoginRequired, PostUnavailable, RateLimited


def summarise_error(exc: BaseException) -> str:
    """A short, human message. Always ends by pointing at the log file."""
    if isinstance(exc, RateLimited):
        base = "Instagram rate-limited this request. Wait a while or add more cookies."
    elif isinstance(exc, LoginRequired):
        base = "This post needs a valid login. Upload a fresh cookies.txt in Settings."
    elif isinstance(exc, PostUnavailable):
        base = "Post is unavailable — it may be deleted or the link is wrong."
    elif isinstance(exc, FetchError):
        base = "Instagram returned an unexpected response."
    elif isinstance(exc, httpx.TimeoutException):
        base = "The connection to Instagram timed out."
    elif isinstance(exc, httpx.HTTPError):
        base = "A network error occurred talking to Instagram."
    else:
        base = "An unexpected error occurred."
    return f"{base} See the log file for full details."


def write_failure_detail(
    error_logger: logging.Logger,
    *,
    job_id: int,
    context: str,
    exc: BaseException,
    url: str | None = None,
    http_status: int | None = None,
) -> None:
    """One detailed block per failure: context line + traceback."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [
        f"---- {now} job={job_id} {context}",
        f"error: {type(exc).__name__}: {exc}",
    ]
    if url:
        lines.append(f"url: {url}")
    if http_status is not None:
        lines.append(f"http_status: {http_status}")
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)).rstrip()
    lines.append(tb)
    error_logger.error("\n".join(lines))
