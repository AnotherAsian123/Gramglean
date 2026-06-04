"""FastAPI application entrypoint.

Serves the JSON API under /api, the job-progress WebSocket under /ws, and the
built React single-page app for everything else.
"""
from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.staticfiles import StaticFiles

from . import __version__
from .api import accounts, cookies, health, jobs, media, settings, ws
from .core.logging_setup import setup_logging
from .db.database import init_db
from .jobs.broker import broker
from .jobs.manager import manager

log = logging.getLogger(__name__)

STATIC_DIR = Path(os.getenv("STATIC_DIR", "/app/static"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    init_db()
    broker.bind_loop(asyncio.get_running_loop())
    manager.start()
    log.info("UnRaiders %s started", __version__)
    try:
        yield
    finally:
        manager.shutdown()


app = FastAPI(title="UnRaiders of the lost Sta", version=__version__, lifespan=lifespan)

# LAN tool: permissive CORS so the Vite dev server can talk to the API in dev.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (health, accounts, jobs, media, settings, cookies):
    app.include_router(module.router)
app.include_router(ws.router)


class SPAStaticFiles(StaticFiles):
    """StaticFiles that falls back to index.html so client-side routes work."""

    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404:
                return await super().get_response("index.html", scope)
            raise


if STATIC_DIR.exists():
    app.mount("/", SPAStaticFiles(directory=str(STATIC_DIR), html=True), name="spa")
else:  # backend-only dev run without a built frontend
    @app.get("/")
    def root() -> dict:
        return {"app": "UnRaiders of the lost Sta", "version": __version__, "api": "/api"}
