from __future__ import annotations

from collections import deque
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from ..core.logging_setup import job_error_log_path, job_log_path
from ..db.database import get_session
from ..db.models import Job, Link
from ..jobs.manager import manager

router = APIRouter()


class RejectedLink(BaseModel):
    url: str
    reason: str


class JobWithLinks(BaseModel):
    job: Job
    links: list[Link]
    rejected: list[RejectedLink] = []


def _tail(path: Path, limit: int) -> list[str]:
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return list(deque(fh, maxlen=limit))


@router.get("/jobs", response_model=list[Job])
def list_jobs(limit: int = 20, session: Session = Depends(get_session)) -> list[Job]:
    limit = max(1, min(100, limit))
    return session.exec(select(Job).order_by(Job.id.desc()).limit(limit)).all()


@router.get("/jobs/{job_id}", response_model=JobWithLinks)
def get_job(job_id: int, session: Session = Depends(get_session)) -> JobWithLinks:
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    links = session.exec(select(Link).where(Link.job_id == job_id).order_by(Link.id)).all()
    return JobWithLinks(job=job, links=list(links))


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: int, session: Session = Depends(get_session)) -> dict:
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if not manager.cancel(job_id):
        raise HTTPException(status_code=409, detail="Job is not running or queued")
    return {"ok": True}


@router.get("/jobs/{job_id}/log")
def job_log(job_id: int, limit: int = 500) -> dict:
    limit = max(1, min(5000, limit))
    return {"lines": _tail(job_log_path(job_id), limit)}


@router.get("/jobs/{job_id}/errors")
def job_errors(job_id: int, limit: int = 2000) -> dict:
    limit = max(1, min(10000, limit))
    return {"lines": _tail(job_error_log_path(job_id), limit)}
