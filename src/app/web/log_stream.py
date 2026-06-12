from __future__ import annotations

import asyncio
import json
from typing import Any, Callable


class LogStream:
    _instance: LogStream | None = None

    def __new__(cls) -> LogStream:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._queues: list[asyncio.Queue] = []
        return cls._instance

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._queues.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        if q in self._queues:
            self._queues.remove(q)

    def emit(self, event_type: str, data: dict[str, Any] | None = None) -> None:
        payload = json.dumps({
            "type": event_type,
            "data": data or {},
        }, ensure_ascii=False)
        for q in self._queues:
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                pass

    @classmethod
    def reset(cls) -> None:
        cls._instance = None
