"""UI-overridable settings, persisted as string key/value rows.

Env vars provide the defaults; a Setting row overrides. Values are coerced by
the type of the default and clamped to sane ranges.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session, select

from ..core import config
from ..db.models import Setting


@dataclass
class EffectiveSettings:
    rate_limit_min: float
    rate_limit_max: float
    download_threads: int


def _defaults() -> dict:
    return {
        "rate_limit_min": config.RATE_LIMIT_MIN,
        "rate_limit_max": config.RATE_LIMIT_MAX,
        "download_threads": config.DOWNLOAD_THREADS,
    }


def get_effective(session: Session) -> EffectiveSettings:
    values = _defaults()
    for row in session.exec(select(Setting)).all():
        if row.key not in values or row.value in (None, ""):
            continue
        default = values[row.key]
        try:
            values[row.key] = type(default)(row.value) if not isinstance(default, float) else float(row.value)
        except (TypeError, ValueError):
            pass
    values["rate_limit_min"] = max(0.0, float(values["rate_limit_min"]))
    values["rate_limit_max"] = max(values["rate_limit_min"], float(values["rate_limit_max"]))
    values["download_threads"] = max(1, min(16, int(values["download_threads"])))
    return EffectiveSettings(**values)


def update_settings(session: Session, updates: dict) -> None:
    valid = _defaults().keys()
    for key, value in updates.items():
        if key not in valid or value is None:
            continue
        row = session.get(Setting, key)
        if row is None:
            session.add(Setting(key=key, value=str(value)))
        else:
            row.value = str(value)
            session.add(row)
