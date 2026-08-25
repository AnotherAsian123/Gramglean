"""Cookie file parsing and least-recently-used rotation.

Cookie files are Netscape-format cookies.txt exports, optionally encrypted at
rest (core.crypto). They are parsed entirely in memory — decrypted plaintext
never touches disk.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Session, select

from ..core import config, crypto
from ..db.database import session_scope
from ..db.models import CookieFile, utcnow


def parse_cookies_txt(data: bytes) -> dict[str, str]:
    """Parse Netscape cookies.txt bytes into {name: value} for instagram.com."""
    jar: dict[str, str] = {}
    for line in data.decode("utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or (line.startswith("#") and not line.startswith("#HttpOnly_")):
            continue
        if line.startswith("#HttpOnly_"):
            line = line[len("#HttpOnly_"):]
        parts = line.split("\t")
        if len(parts) < 7:
            continue
        domain, name, value = parts[0], parts[5], parts[6]
        if "instagram.com" in domain:
            jar[name] = value
    return jar


def load_cookie_jar(cookie: CookieFile) -> dict[str, str]:
    path = config.COOKIES_DIR / cookie.filename
    raw = crypto.decrypt(path.read_bytes())
    return parse_cookies_txt(raw)


def next_cookie(exclude_ids: set[int]) -> Optional[CookieFile]:
    """Pick the least-recently-used enabled cookie file that exists on disk."""
    with session_scope() as session:
        rows = session.exec(select(CookieFile).where(CookieFile.enabled == True)).all()  # noqa: E712
        candidates = [
            c for c in rows
            if c.id not in exclude_ids and (config.COOKIES_DIR / c.filename).exists()
        ]
        if not candidates:
            return None
        candidates.sort(key=lambda c: c.last_used_at or datetime.min)
        chosen = candidates[0]
        session.expunge(chosen)
        return chosen


def mark_used(cookie_id: int) -> None:
    with session_scope() as session:
        row = session.get(CookieFile, cookie_id)
        if row:
            row.last_used_at = utcnow()
            session.add(row)


def mark_status(cookie_id: int, status: str, error: Optional[str] = None) -> None:
    with session_scope() as session:
        row = session.get(CookieFile, cookie_id)
        if row:
            row.status = status
            row.last_error = error
            session.add(row)


def count_enabled(session: Session) -> int:
    rows = session.exec(select(CookieFile).where(CookieFile.enabled == True)).all()  # noqa: E712
    return sum(1 for c in rows if (config.COOKIES_DIR / c.filename).exists())
