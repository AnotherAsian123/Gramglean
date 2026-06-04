import secrets
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import Session, select

from ..core import config, crypto
from ..db.database import get_session
from ..db.models import CookieFile

router = APIRouter(prefix="/api/cookies", tags=["cookies"])


class CookieUpdate(BaseModel):
    enabled: Optional[bool] = None
    label: Optional[str] = None


@router.get("")
def list_cookies(session: Session = Depends(get_session)) -> List[CookieFile]:
    return session.exec(select(CookieFile).order_by(CookieFile.uploaded_at)).all()


@router.post("", status_code=201)
async def upload_cookie(
    file: UploadFile = File(...),
    label: Optional[str] = Form(None),
    session: Session = Depends(get_session),
) -> CookieFile:
    raw = await file.read()
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Cookie file must be UTF-8 text.")
    if "sessionid" not in text:
        raise HTTPException(
            status_code=400,
            detail="That doesn't look like an Instagram cookies.txt "
            "(no 'sessionid' cookie found). Export it while logged in.",
        )

    config.ensure_dirs()
    # Unique stored name so uploads never overwrite earlier cookies (we cycle them).
    stored = f"cookies_{secrets.token_hex(6)}.txt"
    path = config.COOKIES_DIR / stored
    # Encrypt at rest if COOKIE_ENCRYPTION_KEY is configured (else stored plain).
    blob = crypto.encrypt(text.encode("utf-8"))
    path.write_bytes(blob)
    try:
        path.chmod(0o600)
    except OSError:
        pass

    cookie = CookieFile(
        filename=stored,
        original_name=file.filename or stored,
        label=label,
        encrypted=crypto.is_encrypted(blob),
    )
    session.add(cookie)
    session.commit()
    session.refresh(cookie)
    return cookie


@router.patch("/{cookie_id}")
def update_cookie(
    cookie_id: int, payload: CookieUpdate, session: Session = Depends(get_session)
) -> CookieFile:
    cookie = session.get(CookieFile, cookie_id)
    if not cookie:
        raise HTTPException(status_code=404, detail="Cookie not found.")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(cookie, field, value)
    session.add(cookie)
    session.commit()
    session.refresh(cookie)
    return cookie


@router.delete("/{cookie_id}", status_code=204)
def delete_cookie(cookie_id: int, session: Session = Depends(get_session)) -> None:
    cookie = session.get(CookieFile, cookie_id)
    if not cookie:
        raise HTTPException(status_code=404, detail="Cookie not found.")
    (config.COOKIES_DIR / cookie.filename).unlink(missing_ok=True)
    session.delete(cookie)
    session.commit()
