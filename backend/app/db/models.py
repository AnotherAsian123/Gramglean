"""SQLModel table definitions."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.utcnow()


class Account(SQLModel, table=True):
    """An Instagram account on the watchlist."""

    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    full_name: Optional[str] = None
    profile_pic_url: Optional[str] = None
    instagram_userid: Optional[str] = None
    added_at: datetime = Field(default_factory=_utcnow)
    last_synced_at: Optional[datetime] = None
    # Per-account default content toggles, used to pre-fill a new job.
    include_posts: bool = True
    include_reels: bool = True
    include_stories: bool = False


class Job(SQLModel, table=True):
    """A single scrape run for one account."""

    id: Optional[int] = Field(default=None, primary_key=True)
    account_id: int = Field(index=True)
    username: str
    # queued | running | completed | failed | cancelled | rate_limited
    status: str = Field(default="queued", index=True)
    include_posts: bool = True
    include_reels: bool = True
    include_stories: bool = False
    created_at: datetime = Field(default_factory=_utcnow)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    total: int = 0          # resources discovered to download (after incremental skip)
    downloaded: int = 0
    skipped: int = 0        # already present (incremental sync)
    failed: int = 0
    cookie_used: Optional[str] = None
    error: Optional[str] = None
    log_path: Optional[str] = None
    error_log_path: Optional[str] = None


class Media(SQLModel, table=True):
    """One downloaded file. Doubles as the incremental-sync archive: presence of
    a row means the resource has already been fetched and will be skipped."""

    __table_args__ = (
        UniqueConstraint("account_id", "shortcode", "child_index", name="uq_media"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    account_id: int = Field(index=True)
    job_id: Optional[int] = Field(default=None, index=True)
    shortcode: str = Field(index=True)
    child_index: int = 0
    media_type: str = "image"      # image | video
    source: str = "post"           # post | carousel | reel | story
    file_path: str = ""
    width: Optional[int] = None
    height: Optional[int] = None
    taken_at: Optional[datetime] = None
    caption: Optional[str] = None
    downloaded_at: datetime = Field(default_factory=_utcnow)


class CookieFile(SQLModel, table=True):
    """An uploaded Instagram cookies.txt. Multiple may exist; the scraper cycles
    through them to spread load and dodge rate limits. Uploads never overwrite an
    existing file."""

    id: Optional[int] = Field(default=None, primary_key=True)
    filename: str = Field(unique=True)   # stored name under /config/cookies
    original_name: str = ""
    label: Optional[str] = None
    uploaded_at: datetime = Field(default_factory=_utcnow)
    enabled: bool = True
    last_used_at: Optional[datetime] = None
    # unknown | ok | rate_limited | invalid
    status: str = "unknown"
    last_error: Optional[str] = None


class Setting(SQLModel, table=True):
    """Simple key/value store for UI-configurable settings."""

    key: str = Field(primary_key=True)
    value: str = ""
