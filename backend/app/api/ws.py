from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlmodel import Session, select

from ..db.database import get_engine
from ..db.models import Job, Link
from ..jobs.broker import broker

router = APIRouter()


def _snapshot(job_id: int) -> dict | None:
    with Session(get_engine()) as session:
        job = session.get(Job, job_id)
        if job is None:
            return None
        links = session.exec(
            select(Link).where(Link.job_id == job_id).order_by(Link.id)
        ).all()
        return {
            "type": "snapshot",
            "job": job.model_dump(mode="json"),
            "links": [l.model_dump(mode="json") for l in links],
        }


@router.websocket("/ws/jobs/{job_id}")
async def job_socket(websocket: WebSocket, job_id: int) -> None:
    await websocket.accept()
    snapshot = await asyncio.to_thread(_snapshot, job_id)
    if snapshot is None:
        await websocket.close(code=4004)
        return
    await websocket.send_json(snapshot)

    queue = await broker.subscribe(job_id)
    recv_task = asyncio.create_task(websocket.receive_text())
    try:
        while True:
            get_task = asyncio.create_task(queue.get())
            done, _ = await asyncio.wait(
                {get_task, recv_task}, return_when=asyncio.FIRST_COMPLETED
            )
            if recv_task in done:
                # Client sent something or disconnected — either way we're done.
                get_task.cancel()
                break
            event = get_task.result()
            await websocket.send_json(event)
            if event.get("type") == "done":
                recv_task.cancel()
                break
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        for task in (recv_task,):
            if not task.done():
                task.cancel()
        broker.unsubscribe(job_id, queue)
