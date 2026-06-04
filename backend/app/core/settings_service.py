"""Effective settings = environment defaults overridden by values saved in the
Settings UI (stored in the Setting table)."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict

from sqlmodel import Session, select

from ..db.models import Setting
from . import config

# Keys that may be overridden from the UI, with their type + env-derived default.
_DEFAULTS: Dict[str, Any] = {
    "rate_limit_min": config.RATE_LIMIT_MIN,
    "rate_limit_max": config.RATE_LIMIT_MAX,
    "download_threads": config.DOWNLOAD_THREADS,
    "theme": "dark",
    "default_include_posts": True,
    "default_include_reels": True,
    "default_include_stories": False,
}


@dataclass
class EffectiveSettings:
    rate_limit_min: float
    rate_limit_max: float
    download_threads: int
    theme: str
    default_include_posts: bool
    default_include_reels: bool
    default_include_stories: bool

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _coerce(key: str, raw: str) -> Any:
    default = _DEFAULTS[key]
    if isinstance(default, bool):
        return str(raw).strip().lower() in ("1", "true", "yes", "on")
    if isinstance(default, int):
        return int(float(raw))
    if isinstance(default, float):
        return float(raw)
    return raw


def get_effective(session: Session) -> EffectiveSettings:
    values = dict(_DEFAULTS)
    rows = session.exec(select(Setting)).all()
    overrides = {r.key: r.value for r in rows}
    for key in _DEFAULTS:
        if key in overrides and overrides[key] != "":
            try:
                values[key] = _coerce(key, overrides[key])
            except (TypeError, ValueError):
                pass
    # Guard against an inverted range.
    if values["rate_limit_max"] < values["rate_limit_min"]:
        values["rate_limit_max"] = values["rate_limit_min"]
    values["download_threads"] = max(1, int(values["download_threads"]))
    return EffectiveSettings(**values)


def update_settings(session: Session, updates: Dict[str, Any]) -> EffectiveSettings:
    for key, value in updates.items():
        if key not in _DEFAULTS:
            continue
        row = session.get(Setting, key)
        if row is None:
            row = Setting(key=key, value=str(value))
            session.add(row)
        else:
            row.value = str(value)
    session.commit()
    return get_effective(session)
