"""SQLite schema (SQLModel).

A Job is one submitted batch of Instagram links. Each Link tracks one post
through resolve -> fetch -> download. Media rows are the permanent archive —
their existence is what makes re-submitting a link a no-op.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel, UniqueConstraint


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Job(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    status: str = Field(default="queued", index=True)  # queued|running|completed|failed|cancelled
    created_at: datetime = Field(default_factory=utcnow)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    link_count: int = 0
    total: int = 0        # media items discovered
    downloaded: int = 0
    skipped: int = 0      # already archived
    failed: int = 0
    cookie_used: Optional[str] = None
    error: Optional[str] = None  # friendly summary shown in the UI


class Link(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: int = Field(index=True, foreign_key="job.id")
    url: str
    shortcode: str = Field(index=True)
    status: str = Field(default="pending")  # pending|fetching|done|failed|skipped
    username: Optional[str] = None
    caption: Optional[str] = None
    taken_at: Optional[datetime] = None
    media_count: int = 0
    error: Optional[str] = None  # friendly summary shown in the UI


class Media(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("shortcode", "child_index", name="uq_media"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: int = Field(index=True)
    shortcode: str = Field(index=True)
    child_index: int = 0
    media_type: str = "image"  # image|video
    username: Optional[str] = Field(default=None, index=True)
    file_path: str
    width: Optional[int] = None
    height: Optional[int] = None
    taken_at: Optional[datetime] = None
    caption: Optional[str] = None
    downloaded_at: datetime = Field(default_factory=utcnow)


class CookieFile(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    filename: str = Field(unique=True)  # stored name under CONFIG_DIR/cookies
    original_name: str
    uploaded_at: datetime = Field(default_factory=utcnow)
    enabled: bool = True
    encrypted: bool = False
    last_used_at: Optional[datetime] = None
    status: str = "unknown"  # unknown|ok|rate_limited|invalid
    last_error: Optional[str] = None


class Setting(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: str
