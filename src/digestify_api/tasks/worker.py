import asyncio
import logging
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import timedelta
from math import isfinite
from uuid import uuid4

import httpx
from pydantic import JsonValue

from digestify_api.couchdb import (
    DocumentConflict,
    UnresolvedDocumentConflict,
    WriteNotConfirmed,
)
from digestify_api.tasks.service import TaskService
from digestify_api.tasks.task import BUCKET_COUNT, LostLease, Task, bucket_for

logger = logging.getLogger(__name__)
Handler = Callable[[Task], Awaitable[JsonValue]]
PERSISTENCE_ERRORS = (
    httpx.HTTPError,
    DocumentConflict,
    UnresolvedDocumentConflict,
    WriteNotConfirmed,
)


@dataclass(frozen=True)
class Partition:
    index: int = 0
    count: int = 1

    def __post_init__(self) -> None:
        if not 1 <= self.count <= BUCKET_COUNT or not 0 <= self.index < self.count:
            raise ValueError("Require 0 <= index < count <= 256.")

    @property
    def buckets(self) -> tuple[int, ...]:
        return tuple(range(self.index, BUCKET_COUNT, self.count))

    def owns(self, key: str) -> bool:
        return bucket_for(key) % self.count == self.index


class Worker:
    def __init__(
        self,
        service: TaskService,
        handlers: Mapping[str, Handler],
        *,
        worker_id: str | None = None,
        partition: Partition = Partition(),
        concurrency: int = 10,
        lease: timedelta = timedelta(minutes=10),
        poll_interval: float = 15,
        heartbeat_interval: float | None = None,
    ) -> None:
        heartbeat = (
            lease.total_seconds() / 3
            if heartbeat_interval is None
            else heartbeat_interval
        )
        if concurrency < 1 or lease <= timedelta(0):
            raise ValueError("Concurrency and lease must be positive.")
        if not isfinite(poll_interval) or poll_interval <= 0:
            raise ValueError("Poll interval must be finite and positive.")
        if not isfinite(heartbeat) or not 0 < heartbeat < lease.total_seconds() / 2:
            raise ValueError("Heartbeat must be positive and less than half the lease.")
        if not handlers:
            raise ValueError("At least one handler is required.")
        self._service = service
        self._handlers = dict(handlers)
        self._worker_id = worker_id or str(uuid4())
        self._partition = partition
        self._concurrency = concurrency
        self._lease = lease
        self._poll_interval = poll_interval
        self._heartbeat_interval = heartbeat
        self._wakeup = asyncio.Event()
        self._running: dict[str, asyncio.Task[None]] = {}
        self._started = False

    async def run(self) -> None:
        """Run until cancelled; cancel and await handlers before returning."""
        if self._started:
            raise RuntimeError("This worker is already running.")
        self._started = True
        watcher = asyncio.create_task(self._watch())
        try:
            await self._schedule_loop()
        finally:
            watcher.cancel()
            executions = list(self._running.values())
            for execution in executions:
                execution.cancel()
            await asyncio.gather(watcher, *executions, return_exceptions=True)
            self._running.clear()
            self._started = False

    async def _schedule_loop(self) -> None:
        while True:
            self._wakeup.clear()
            try:
                await self._tick()
            except PERSISTENCE_ERRORS:
                logger.warning(
                    "Task scan failed; retrying on the next poll", exc_info=True
                )
            try:
                await asyncio.wait_for(self._wakeup.wait(), self._poll_interval)
            except TimeoutError:
                pass

    async def _watch(self) -> None:
        since = "now"
        while True:
            try:
                async for sequence in self._service.changes(since):
                    since = sequence
                    self._wakeup.set()
            except httpx.HTTPError:
                logger.warning("Task changes feed disconnected", exc_info=True)
            await asyncio.sleep(self._poll_interval)

    async def _tick(self) -> None:
        if len(self._running) >= self._concurrency:
            return
        candidates = await self._service.candidates(
            self._partition.buckets, tuple(self._handlers)
        )
        for candidate in candidates:
            if len(self._running) >= self._concurrency:
                break
            if candidate.id in self._running:
                continue
            try:
                task = await self._service.claim(
                    candidate.id, self._worker_id, self._lease
                )
            except PERSISTENCE_ERRORS:
                logger.warning(
                    "Task %s could not be claimed", candidate.id, exc_info=True
                )
                continue
            if task is not None:
                execution = asyncio.create_task(self._execute(task))
                self._running[task.id] = execution
                execution.add_done_callback(
                    lambda done, task_id=task.id: self._done(task_id, done)
                )

    def _done(self, task_id: str, execution: asyncio.Task[None]) -> None:
        self._running.pop(task_id, None)
        if not execution.cancelled() and execution.exception() is not None:
            logger.error(
                "Task execution failed: %s", task_id, exc_info=execution.exception()
            )
        self._wakeup.set()

    async def _heartbeat(self, task: Task) -> None:
        assert task.claim_token is not None
        while True:
            await asyncio.sleep(self._heartbeat_interval)
            await asyncio.wait_for(
                self._service.renew(task.id, task.claim_token, self._lease),
                timeout=self._heartbeat_interval,
            )

    async def _execute(self, task: Task) -> None:
        assert task.claim_token is not None
        handler = asyncio.ensure_future(
            self._handlers[task.kind](task.model_copy(deep=True))
        )
        heartbeat = asyncio.create_task(self._heartbeat(task))
        try:
            done, _ = await asyncio.wait(
                (handler, heartbeat), return_when=asyncio.FIRST_COMPLETED
            )
            if heartbeat in done:
                heartbeat.result()
                return
            heartbeat.cancel()
            await asyncio.gather(heartbeat, return_exceptions=True)
            result: JsonValue = None
            error = None
            try:
                result = handler.result()
            except Exception as failure:
                error = f"{type(failure).__name__}: {failure}"[:2000]
                logger.exception("Handler failed for task %s", task.id)
            await self._service.finish(
                task.id, task.claim_token, result=result, error=error
            )
        except (LostLease, TimeoutError, *PERSISTENCE_ERRORS):
            logger.warning(
                "Task %s lost its lease or persistence confirmation",
                task.id,
                exc_info=True,
            )
        finally:
            handler.cancel()
            heartbeat.cancel()
            await asyncio.gather(handler, heartbeat, return_exceptions=True)
