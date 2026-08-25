from __future__ import annotations

import mimetypes
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, Response, StreamingResponse
from sqlmodel import Session, func, select

from ..db.database import get_session
from ..db.models import Media

router = APIRouter()


@router.get("/media")
def list_media(
    username: Optional[str] = None,
    media_type: Optional[str] = None,
    offset: int = 0,
    limit: int = 60,
    session: Session = Depends(get_session),
) -> dict:
    limit = max(1, min(200, limit))
    query = select(Media)
    count_query = select(func.count()).select_from(Media)
    if username:
        query = query.where(Media.username == username)
        count_query = count_query.where(Media.username == username)
    if media_type in ("image", "video"):
        query = query.where(Media.media_type == media_type)
        count_query = count_query.where(Media.media_type == media_type)
    total = session.exec(count_query).one()
    rows = session.exec(
        query.order_by(Media.taken_at.desc(), Media.id.desc()).offset(offset).limit(limit)
    ).all()
    return {"total": total, "items": rows}


@router.get("/media/usernames")
def list_usernames(session: Session = Depends(get_session)) -> list[dict]:
    rows = session.exec(
        select(Media.username, func.count())
        .group_by(Media.username)
        .order_by(func.count().desc())
    ).all()
    return [{"username": u or "unknown", "count": c} for u, c in rows]


_CHUNK = 64 * 1024


@router.get("/media/{media_id}/file")
def media_file(media_id: int, request: Request, session: Session = Depends(get_session)):
    row = session.get(Media, media_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Media not found")
    path = Path(row.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File missing on disk")
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"

    range_header = request.headers.get("range")
    if range_header is None:
        return FileResponse(path, media_type=mime, filename=path.name)
    return _range_response(path, mime, range_header)


def _range_response(path: Path, mime: str, range_header: str):
    """Minimal single-range implementation so video scrubbing works."""
    size = os.path.getsize(path)
    try:
        unit, _, spec = range_header.partition("=")
        if unit.strip().lower() != "bytes":
            raise ValueError
        start_s, _, end_s = spec.split(",")[0].partition("-")
        start = int(start_s) if start_s else size - int(end_s)
        end = int(end_s) if start_s and end_s else size - 1
        if start < 0 or start > end:
            raise ValueError
        end = min(end, size - 1)
    except (ValueError, TypeError):
        return Response(status_code=416, headers={"Content-Range": f"bytes */{size}"})

    length = end - start + 1

    def stream():
        with open(path, "rb") as fh:
            fh.seek(start)
            remaining = length
            while remaining > 0:
                chunk = fh.read(min(_CHUNK, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    headers = {
        "Content-Range": f"bytes {start}-{end}/{size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(length),
    }
    return StreamingResponse(stream(), status_code=206, media_type=mime, headers=headers)
