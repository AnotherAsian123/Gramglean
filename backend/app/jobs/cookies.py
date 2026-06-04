"""Cookie-file management and rotation.

Multiple Instagram ``cookies.txt`` files can be uploaded (each typically from a
different account / browser session). Uploads are stored side by side and are
never overwritten, so the scraper can cycle through them: when one trips a rate
limit or lock, we rotate to the least-recently-used enabled cookie and carry on.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from sqlmodel import select

from ..core import config
from ..db.database import session_scope
from ..db.models import CookieFile


def cookie_path(cookie: CookieFile) -> Path:
    return config.COOKIES_DIR / cookie.filename


def next_cookie(exclude_ids: Iterable[int] = ()) -> Optional[CookieFile]:
    """Least-recently-used enabled cookie that isn't excluded. Returns a detached
    copy so callers can use it outside the session."""
    exclude = set(exclude_ids)
    with session_scope() as session:
        rows = session.exec(
            select(CookieFile).where(CookieFile.enabled == True)  # noqa: E712
        ).all()
        candidates = [c for c in rows if c.id not in exclude and cookie_path(c).exists()]
        if not candidates:
            return None
        # None (never used) sorts before any timestamp.
        candidates.sort(key=lambda c: (c.last_used_at or datetime.min))
        chosen = candidates[0]
        session.expunge(chosen)
        return chosen


def mark_used(cookie_id: int) -> None:
    with session_scope() as session:
        row = session.get(CookieFile, cookie_id)
        if row:
            row.last_used_at = datetime.utcnow()
            session.add(row)


def mark_status(cookie_id: int, status: str, error: Optional[str] = None) -> None:
    with session_scope() as session:
        row = session.get(CookieFile, cookie_id)
        if row:
            row.status = status
            row.last_error = error
            session.add(row)


def count_enabled() -> int:
    with session_scope() as session:
        rows = session.exec(
            select(CookieFile).where(CookieFile.enabled == True)  # noqa: E712
        ).all()
        return sum(1 for c in rows if cookie_path(c).exists())
