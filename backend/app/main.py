"""Gramglean — paste Instagram links, archive every image in them."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .api import cookies, health, jobs, media, queue, settings, ws
from .core import config
from .core.logging_setup import prune_old_job_logs, setup_logging
from .db.database import init_db
from .jobs.broker import broker
from .jobs.manager import manager

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    config.ensure_dirs()
    init_db()
    prune_old_job_logs()
    broker.bind_loop(asyncio.get_running_loop())
    log.info("Gramglean started (port %d)", config.PORT)
    yield
    manager.shutdown()


app = FastAPI(title="Gramglean", lifespan=lifespan)

if config.DEV_CORS:
    from fastapi.middleware.cors import CORSMiddleware

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(health.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")
app.include_router(queue.router, prefix="/api")
app.include_router(media.router, prefix="/api")
app.include_router(cookies.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.include_router(ws.router)


# Unknown /api paths must return JSON, never fall through to the SPA.
@app.get("/api/{_rest:path}", include_in_schema=False)
def api_not_found(_rest: str) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": "Not found"})


class SPAStaticFiles(StaticFiles):
    """Serve the built SPA; unknown paths fall back to index.html."""

    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code == 404:
                return await super().get_response("index.html", scope)
            raise


if config.STATIC_DIR.is_dir():
    app.mount("/", SPAStaticFiles(directory=str(config.STATIC_DIR), html=True), name="spa")
