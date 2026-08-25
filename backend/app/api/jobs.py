from __future__ import annotations

from collections import deque
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from ..core.logging_setup import job_error_log_path, job_log_path
from ..db.database import get_session
from ..db.models import Job, Link
from ..insta.urls import InvalidLink, shortcode_from_url
from ..jobs.manager import manager

router = APIRouter()


class JobCreate(BaseModel):
    links: list[str]


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


@router.post("/jobs", status_code=201, response_model=JobWithLinks)
def create_job(payload: JobCreate, session: Session = Depends(get_session)) -> JobWithLinks:
    seen: set[str] = set()
    accepted: list[tuple[str, str]] = []  # (url, shortcode)
    rejected: list[RejectedLink] = []
    for raw in payload.links:
        url = raw.strip()
        if not url:
            continue
        try:
            shortcode = shortcode_from_url(url)
        except InvalidLink as exc:
            rejected.append(RejectedLink(url=url, reason=str(exc)))
            continue
        if shortcode in seen:
            rejected.append(RejectedLink(url=url, reason="Duplicate of another link in this batch."))
            continue
        seen.add(shortcode)
        accepted.append((url, shortcode))

    if not accepted:
        detail = "No valid Instagram post links found."
        if rejected:
            detail += " " + "; ".join(r.reason for r in rejected[:3])
        raise HTTPException(status_code=400, detail=detail)

    job = Job(link_count=len(accepted))
    session.add(job)
    session.commit()
    session.refresh(job)
    links = [Link(job_id=job.id, url=url, shortcode=code) for url, code in accepted]
    for link in links:
        session.add(link)
    session.commit()
    for link in links:
        session.refresh(link)

    manager.submit(job.id)
    return JobWithLinks(job=job, links=links, rejected=rejected)


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
