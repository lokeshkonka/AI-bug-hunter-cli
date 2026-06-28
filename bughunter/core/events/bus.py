import asyncio
from typing import Callable, Coroutine, Any, List, Dict
from bughunter.models.event import BugHunterEvent, EventType

EventHandler = Callable[[BugHunterEvent], Coroutine[Any, Any, None]]

class AsyncEventBus:
    def __init__(self):
        self._subscribers: Dict[EventType, List[EventHandler]] = {}
        self._global_subscribers: List[EventHandler] = []
        self._queue: asyncio.Queue[BugHunterEvent] = asyncio.Queue()
        self._worker_task: asyncio.Task | None = None

    def subscribe(self, event_type: EventType, handler: EventHandler):
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)

    def subscribe_all(self, handler: EventHandler):
        self._global_subscribers.append(handler)

    async def publish(self, event: BugHunterEvent):
        await self._queue.put(event)

    async def _worker(self):
        while True:
            event = await self._queue.get()
            handlers = self._global_subscribers.copy()
            if event.type in self._subscribers:
                handlers.extend(self._subscribers[event.type])
            
            for handler in handlers:
                try:
                    await handler(event)
                except Exception as e:
                    # In a real app, log this properly.
                    print(f"Error in event handler: {e}")
            
            self._queue.task_done()

    def start(self):
        if self._worker_task is None:
            self._worker_task = asyncio.create_task(self._worker())

    async def stop(self):
        if self._worker_task:
            # Wait for all published events to be processed
            await self._queue.join()
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None
