"""In-process async pub/sub bus.

Redis-ready: the publish/subscribe surface mirrors redis.asyncio.Redis so swapping
in Redis pub/sub later is a one-file change. For the demo we keep it local.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections import defaultdict
from collections.abc import AsyncIterator
from typing import Any

_Event = dict[str, Any]


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue[_Event]]] = defaultdict(set)

    async def publish(self, channel: str, payload: _Event) -> None:
        for q in list(self._subscribers.get(channel, ())):
            # Non-blocking: drop the oldest if a slow consumer is backing up.
            if q.full():
                with contextlib.suppress(asyncio.QueueEmpty):
                    q.get_nowait()
            await q.put(payload)

    async def subscribe(self, channel: str) -> AsyncIterator[_Event]:
        q: asyncio.Queue[_Event] = asyncio.Queue(maxsize=64)
        self._subscribers[channel].add(q)
        try:
            while True:
                yield await q.get()
        finally:
            self._subscribers[channel].discard(q)


bus = EventBus()
