from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, select

from ..db.database import get_session
from ..db.models import Account, Job
from ..jobs.manager import manager
from .validation import normalize_username

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


class JobCreate(BaseModel):
    username: str
    include_posts: bool = True
    include_reels: bool = True
    include_stories: bool = False


def _tail(path: Optional[str], limit: int) -> List[str]:
    if not path:
        return []
    p = Path(path)
    if not p.exists():
        return []
    with open(p, "r", encoding="utf-8", errors="replace") as fh:
        lines = fh.read().splitlines()
    return lines[-limit:]


@router.post("", status_code=201)
def create_job(payload: JobCreate, session: Session = Depends(get_session)) -> Job:
    if not (payload.include_posts or payload.include_reels or payload.include_stories):
        raise HTTPException(status_code=400, detail="Select at least one content type.")
    username = normalize_username(payload.username)
    account = session.exec(select(Account).where(Account.username == username)).first()
    if account is None:
        account = Account(
            username=username,
            include_posts=payload.include_posts,
            include_reels=payload.include_reels,
            include_stories=payload.include_stories,
        )
        session.add(account)
        session.commit()
        session.refresh(account)

    job = Job(
        account_id=account.id,
        username=username,
        status="queued",
        include_posts=payload.include_posts,
        include_reels=payload.include_reels,
        include_stories=payload.include_stories,
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    manager.submit(job.id)
    return job


@router.get("")
def list_jobs(
    limit: int = Query(50, le=200),
    account_id: Optional[int] = None,
    session: Session = Depends(get_session),
) -> List[Job]:
    query = select(Job).order_by(Job.created_at.desc()).limit(limit)
    if account_id is not None:
        query = select(Job).where(Job.account_id == account_id).order_by(
            Job.created_at.desc()
        ).limit(limit)
    return session.exec(query).all()


@router.get("/{job_id}")
def get_job(job_id: int, session: Session = Depends(get_session)) -> Job:
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job


@router.get("/{job_id}/log")
def get_job_log(
    job_id: int, limit: int = Query(500, le=5000), session: Session = Depends(get_session)
) -> dict:
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return {"lines": _tail(job.log_path, limit)}


@router.get("/{job_id}/errors")
def get_job_errors(
    job_id: int, limit: int = Query(1000, le=10000), session: Session = Depends(get_session)
) -> dict:
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return {"lines": _tail(job.error_log_path, limit)}


@router.post("/{job_id}/cancel")
def cancel_job(job_id: int, session: Session = Depends(get_session)) -> dict:
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job.status not in ("queued", "running"):
        raise HTTPException(status_code=409, detail=f"Job is already {job.status}.")
    cancelled = manager.cancel(job_id)
    return {"cancelled": cancelled}
