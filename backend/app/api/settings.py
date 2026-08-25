from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session

from ..core import config, crypto
from ..core.settings_service import get_effective, update_settings
from ..db.database import get_session
from ..insta.cookies import count_enabled

router = APIRouter()


class SettingsUpdate(BaseModel):
    rate_limit_min: float | None = None
    rate_limit_max: float | None = None
    download_threads: int | None = None


def _payload(session: Session) -> dict:
    effective = get_effective(session)
    return {
        "rate_limit_min": effective.rate_limit_min,
        "rate_limit_max": effective.rate_limit_max,
        "download_threads": effective.download_threads,
        "cookies_available": count_enabled(session),
        "cookie_encryption": crypto.encryption_enabled(),
        "env_defaults": {
            "rate_limit_min": config.RATE_LIMIT_MIN,
            "rate_limit_max": config.RATE_LIMIT_MAX,
            "download_threads": config.DOWNLOAD_THREADS,
        },
    }


@router.get("/settings")
def get_settings(session: Session = Depends(get_session)) -> dict:
    return _payload(session)


@router.put("/settings")
def put_settings(payload: SettingsUpdate, session: Session = Depends(get_session)) -> dict:
    update_settings(session, payload.model_dump(exclude_none=True))
    session.commit()
    return _payload(session)
