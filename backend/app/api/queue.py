"""The download queue: links are collected here and nothing downloads until
the user starts the queue, which turns every queued item into one Job."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from ..db.database import get_session
from ..db.models import Job, Link, QueueItem
from ..insta.urls import InvalidLink, shortcode_from_url
from ..jobs.manager import manager
from .jobs import JobWithLinks, RejectedLink

router = APIRouter()


class QueueAdd(BaseModel):
    links: list[str]


class QueueAddResult(BaseModel):
    added: list[QueueItem]
    rejected: list[RejectedLink]


@router.get("/queue", response_model=list[QueueItem])
def list_queue(session: Session = Depends(get_session)) -> list[QueueItem]:
    return session.exec(select(QueueItem).order_by(QueueItem.id)).all()


@router.post("/queue", response_model=QueueAddResult)
def add_to_queue(payload: QueueAdd, session: Session = Depends(get_session)) -> QueueAddResult:
    existing = {
        item.shortcode for item in session.exec(select(QueueItem)).all()
    }
    added: list[QueueItem] = []
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
        if shortcode in existing:
            rejected.append(RejectedLink(url=url, reason="Already in the queue."))
            continue
        existing.add(shortcode)
        item = QueueItem(url=url, shortcode=shortcode)
        session.add(item)
        added.append(item)
    session.commit()
    for item in added:
        session.refresh(item)
    return QueueAddResult(added=added, rejected=rejected)


@router.delete("/queue/{item_id}")
def remove_queue_item(item_id: int, session: Session = Depends(get_session)) -> dict:
    item = session.get(QueueItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Queue item not found")
    session.delete(item)
    session.commit()
    return {"ok": True}


@router.delete("/queue")
def clear_queue(session: Session = Depends(get_session)) -> dict:
    items = session.exec(select(QueueItem)).all()
    for item in items:
        session.delete(item)
    session.commit()
    return {"ok": True, "removed": len(items)}


@router.post("/queue/start", status_code=201, response_model=JobWithLinks)
def start_queue(session: Session = Depends(get_session)) -> JobWithLinks:
    items = session.exec(select(QueueItem).order_by(QueueItem.id)).all()
    if not items:
        raise HTTPException(status_code=400, detail="The queue is empty — add some links first.")

    job = Job(link_count=len(items))
    session.add(job)
    session.commit()
    session.refresh(job)

    links = [Link(job_id=job.id, url=i.url, shortcode=i.shortcode) for i in items]
    for link in links:
        session.add(link)
    for item in items:
        session.delete(item)
    session.commit()
    for link in links:
        session.refresh(link)

    manager.submit(job.id)
    return JobWithLinks(job=job, links=links)
