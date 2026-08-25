from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import Session, select

from ..core import config, crypto
from ..db.database import get_session
from ..db.models import CookieFile
from ..insta.cookies import parse_cookies_txt

router = APIRouter()


@router.get("/cookies", response_model=list[CookieFile])
def list_cookies(session: Session = Depends(get_session)) -> list[CookieFile]:
    return session.exec(select(CookieFile).order_by(CookieFile.uploaded_at)).all()


@router.post("/cookies", status_code=201, response_model=CookieFile)
async def upload_cookie(file: UploadFile, session: Session = Depends(get_session)) -> CookieFile:
    raw = await file.read()
    if len(raw) > 1024 * 1024:
        raise HTTPException(status_code=400, detail="Cookie file is too large.")
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Not a text file — export cookies in Netscape cookies.txt format.")
    jar = parse_cookies_txt(raw)
    if "sessionid" not in jar:
        raise HTTPException(
            status_code=400,
            detail="No Instagram sessionid found — export cookies.txt while logged in to instagram.com.",
        )

    filename = f"cookies_{secrets.token_hex(6)}.txt"
    path = config.COOKIES_DIR / filename
    path.write_bytes(crypto.encrypt(raw))
    try:
        path.chmod(0o600)
    except OSError:
        pass

    row = CookieFile(
        filename=filename,
        original_name=file.filename or filename,
        encrypted=crypto.encryption_enabled(),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


class CookiePatch(BaseModel):
    enabled: bool | None = None
    original_name: str | None = None


@router.patch("/cookies/{cookie_id}", response_model=CookieFile)
def patch_cookie(cookie_id: int, payload: CookiePatch, session: Session = Depends(get_session)) -> CookieFile:
    row = session.get(CookieFile, cookie_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Cookie not found")
    if payload.enabled is not None:
        row.enabled = payload.enabled
    if payload.original_name:
        row.original_name = payload.original_name.strip()[:100]
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


@router.delete("/cookies/{cookie_id}")
def delete_cookie(cookie_id: int, session: Session = Depends(get_session)) -> dict:
    row = session.get(CookieFile, cookie_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Cookie not found")
    (config.COOKIES_DIR / row.filename).unlink(missing_ok=True)
    session.delete(row)
    session.commit()
    return {"ok": True}
