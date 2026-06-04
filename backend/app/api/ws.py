import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlmodel import Session

from ..db.database import get_engine
from ..db.models import Job
from ..jobs.broker import broker

router = APIRouter(tags=["ws"])


@router.websocket("/ws/jobs/{job_id}")
async def job_progress(websocket: WebSocket, job_id: int) -> None:
    await websocket.accept()
    # Send a snapshot first so a late subscriber sees current state immediately.
    with Session(get_engine()) as session:
        job = session.get(Job, job_id)
        if job:
            await websocket.send_json(
                {
                    "type": "snapshot",
                    "job_id": job_id,
                    "status": job.status,
                    "total": job.total,
                    "downloaded": job.downloaded,
                    "skipped": job.skipped,
                    "failed": job.failed,
                    "error": job.error,
                }
            )

    queue = await broker.subscribe(job_id)
    try:
        while True:
            event = await queue.get()
            await websocket.send_json(event)
    except WebSocketDisconnect:
        pass
    except asyncio.CancelledError:
        raise
    finally:
        broker.unsubscribe(job_id, queue)
