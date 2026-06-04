"""Tiny in-process pub/sub bridging the worker threads to WebSocket clients.

Workers run in a thread pool and call ``publish`` (thread-safe). Subscribers are
asyncio coroutines (the WebSocket handlers) living on the main event loop.
"""
from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any, Dict, Set


class ProgressBroker:
    def __init__(self) -> None:
        self._subs: Dict[int, Set[asyncio.Queue]] = defaultdict(set)
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    async def subscribe(self, job_id: int) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._subs[job_id].add(q)
        return q

    def unsubscribe(self, job_id: int, q: asyncio.Queue) -> None:
        subs = self._subs.get(job_id)
        if subs:
            subs.discard(q)
            if not subs:
                self._subs.pop(job_id, None)

    def publish(self, job_id: int, event: Dict[str, Any]) -> None:
        """Called from worker threads. Marshals the event onto the event loop."""
        loop = self._loop
        if loop is None:
            return
        for q in list(self._subs.get(job_id, ())):
            try:
                loop.call_soon_threadsafe(q.put_nowait, event)
            except RuntimeError:
                # Loop is closed/shutting down.
                pass


broker = ProgressBroker()
