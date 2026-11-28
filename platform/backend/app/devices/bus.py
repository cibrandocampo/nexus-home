"""In-process event bus for device changes (one app instance, one event loop).

The poller publishes; the history collector (and later a Home Assistant adapter or a live push to
browsers) subscribes. A subscriber that falls behind loses its oldest events, never blocks the
poller.
"""

import asyncio
from dataclasses import dataclass

QUEUE_SIZE = 256


@dataclass(frozen=True)
class StateChanged:
    device_pk: int
    rev: int


@dataclass(frozen=True)
class WentOnline:
    device_pk: int


@dataclass(frozen=True)
class WentOffline:
    device_pk: int


@dataclass(frozen=True)
class Rebooted:
    device_pk: int
    uptime_s: int


Event = StateChanged | WentOnline | WentOffline | Rebooted


class Bus:
    def __init__(self) -> None:
        self._queues: list[asyncio.Queue[Event]] = []

    def subscribe(self, size: int = QUEUE_SIZE) -> asyncio.Queue[Event]:
        queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=size)
        self._queues.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[Event]) -> None:
        if queue in self._queues:
            self._queues.remove(queue)

    def publish(self, event: Event) -> None:
        for queue in self._queues:
            if queue.full():
                queue.get_nowait()  # drop the oldest
            queue.put_nowait(event)

    def reset(self) -> None:
        self._queues.clear()


bus = Bus()
