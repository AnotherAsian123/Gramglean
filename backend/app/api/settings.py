from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session

from ..core import config, crypto
from ..core.settings_service import get_effective, update_settings
from ..db.database import get_session
from ..jobs.cookies import count_enabled

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsUpdate(BaseModel):
    rate_limit_min: Optional[float] = None
    rate_limit_max: Optional[float] = None
    download_threads: Optional[int] = None
    theme: Optional[str] = None
    default_include_posts: Optional[bool] = None
    default_include_reels: Optional[bool] = None
    default_include_stories: Optional[bool] = None


def _payload(session: Session) -> dict:
    eff = get_effective(session)
    data = eff.as_dict()
    data["cookies_available"] = count_enabled()
    data["cookie_encryption"] = crypto.encryption_enabled()
    # Surface which knobs come from the environment so the UI can hint at it.
    data["env_defaults"] = {
        "download_threads": config.DOWNLOAD_THREADS,
        "max_concurrent_jobs": config.MAX_CONCURRENT_JOBS,
        "rate_limit_min": config.RATE_LIMIT_MIN,
        "rate_limit_max": config.RATE_LIMIT_MAX,
    }
    return data


@router.get("")
def read_settings(session: Session = Depends(get_session)) -> dict:
    return _payload(session)


@router.put("")
def write_settings(payload: SettingsUpdate, session: Session = Depends(get_session)) -> dict:
    update_settings(session, payload.model_dump(exclude_none=True))
    return _payload(session)
