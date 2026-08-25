"""In-process pub/sub bridging worker threads to WebSocket subscribers."""
from __future__ import annotations

import asyncio
from typing import Dict, Set


class ProgressBroker:
    def __init__(self) -> None:
        self._subs: Dict[int, Set[asyncio.Queue]] = {}
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    async def subscribe(self, job_id: int) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._subs.setdefault(job_id, set()).add(queue)
        return queue

    def unsubscribe(self, job_id: int, queue: asyncio.Queue) -> None:
        subs = self._subs.get(job_id)
        if subs:
            subs.discard(queue)
            if not subs:
                self._subs.pop(job_id, None)

    def publish(self, job_id: int, event: dict) -> None:
        """Safe to call from any thread."""
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        for queue in self._subs.get(job_id, set()).copy():
            try:
                loop.call_soon_threadsafe(queue.put_nowait, event)
            except RuntimeError:
                pass  # loop shut down mid-publish


broker = ProgressBroker()
