from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import func
from sqlmodel import Session, select

from ..core import config
from ..db.database import get_session
from ..db.models import Media

router = APIRouter(prefix="/api/media", tags=["media"])


@router.get("")
def list_media(
    account_id: Optional[int] = None,
    source: Optional[str] = Query(None, description="post|carousel|reel|story"),
    media_type: Optional[str] = Query(None, description="image|video"),
    limit: int = Query(60, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
) -> dict:
    filters = []
    if account_id is not None:
        filters.append(Media.account_id == account_id)
    if source:
        filters.append(Media.source == source)
    if media_type:
        filters.append(Media.media_type == media_type)

    count_q = select(func.count()).select_from(Media)
    page_q = select(Media).order_by(Media.taken_at.desc(), Media.id.desc())
    for f in filters:
        count_q = count_q.where(f)
        page_q = page_q.where(f)

    total = session.exec(count_q).one()
    items = session.exec(page_q.offset(offset).limit(limit)).all()
    return {"total": total, "items": items}


@router.get("/{media_id}/file")
def get_media_file(media_id: int, session: Session = Depends(get_session)) -> FileResponse:
    media = session.get(Media, media_id)
    if not media:
        raise HTTPException(status_code=404, detail="Media not found.")
    path = Path(media.file_path).resolve()
    download_root = config.DOWNLOAD_DIR.resolve()
    # Defence in depth: never serve anything outside the downloads volume.
    if download_root not in path.parents:
        raise HTTPException(status_code=403, detail="Path outside download directory.")
    if not path.exists():
        raise HTTPException(status_code=404, detail="File missing on disk.")
    return FileResponse(path)
