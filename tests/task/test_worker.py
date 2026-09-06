import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock

import httpx
import pytest

from digestify_api.couchdb import WriteNotConfirmed
from digestify_api.tasks import Partition, Task, TaskService, Worker
from tests.task.conftest import InMemoryCouch


async def drain(worker: Worker) -> None:
    async with asyncio.timeout(2):
        await asyncio.gather(*list(worker._running.values()))


async def test_worker_executes_and_tracks_result(service: TaskService) -> None:
    task = await service.create("email")
    handler = AsyncMock(return_value={"sent": True})
    worker = Worker(service, {"email": handler})
    await worker._tick()
    await drain(worker)
    handler.assert_awaited_once()
    stored = await service.get(task.id)
    assert stored is not None and stored.status == "succeeded"
    assert stored.last_result == {"sent": True}
    await worker._tick()
    handler.assert_awaited_once()


async def test_handler_failure_is_persisted_for_retry(service: TaskService) -> None:
    task = await service.create("email")
    worker = Worker(service, {"email": AsyncMock(side_effect=ValueError("bad input"))})
    await worker._tick()
    await drain(worker)
    stored = await service.get(task.id)
    assert stored is not None and stored.status == "pending"
    assert stored.last_error == "ValueError: bad input"
    assert stored.attempts == 1


async def test_uncertain_or_conflicted_claim_never_runs_handler(
    service: TaskService, couch: InMemoryCouch
) -> None:
    uncertain = await service.create("email")
    conflicted = await service.create("email")
    couch.docs[conflicted.id]["_conflicts"] = ["2-diverged"]
    couch.next_write_status = 202
    handler = AsyncMock()
    worker = Worker(service, {"email": handler})
    await worker._tick()
    await drain(worker)
    handler.assert_not_awaited()
    assert couch.docs[uncertain.id]["status"] == "running"


async def test_two_partitions_cover_each_task_once(service: TaskService) -> None:
    for number in range(20):
        await service.create("email", partition_key=f"user:{number}")
    calls: list[tuple[int, Task]] = []

    async def first(task: Task) -> None:
        calls.append((0, task))

    async def second(task: Task) -> None:
        calls.append((1, task))

    workers = [
        Worker(service, {"email": first}, partition=Partition(0, 2), concurrency=30),
        Worker(service, {"email": second}, partition=Partition(1, 2), concurrency=30),
    ]
    for worker in workers:
        await worker._tick()
    for worker in workers:
        await drain(worker)
    assert len(calls) == len({task.id for _, task in calls}) == 20
    assert {index for index, _ in calls} == {0, 1}
    assert all(Partition(index, 2).owns(task.partition_key) for index, task in calls)


async def test_cancellation_stops_running_handler_on_heartbeat(
    service: TaskService,
) -> None:
    task = await service.create("email")
    started, stopped = asyncio.Event(), asyncio.Event()

    async def handler(task: Task) -> None:
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    worker = Worker(service, {"email": handler}, heartbeat_interval=0.01)
    await worker._tick()
    async with asyncio.timeout(2):
        await started.wait()
        await service.cancel(task.id)
        await stopped.wait()
        await drain(worker)
    stored = await service.get(task.id)
    assert stored is not None and stored.status == "cancelled"


async def test_uncertain_renewal_stops_handler(
    service: TaskService, monkeypatch: pytest.MonkeyPatch
) -> None:
    await service.create("email")
    stopped = asyncio.Event()

    async def handler(task: Task) -> None:
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    monkeypatch.setattr(
        service, "renew", AsyncMock(side_effect=WriteNotConfirmed("task"))
    )
    worker = Worker(service, {"email": handler}, heartbeat_interval=0.01)
    await worker._tick()
    await drain(worker)
    assert stopped.is_set()


async def test_heartbeat_renews_until_handler_finishes(
    service: TaskService, monkeypatch: pytest.MonkeyPatch
) -> None:
    task = await service.create("email")
    renewed = asyncio.Event()
    original_renew = service.renew

    async def renew(*args, **kwargs):
        result = await original_renew(*args, **kwargs)
        renewed.set()
        return result

    async def handler(task: Task) -> None:
        await renewed.wait()

    monkeypatch.setattr(service, "renew", renew)
    worker = Worker(service, {"email": handler}, heartbeat_interval=0.01)
    await worker._tick()
    await drain(worker)
    assert renewed.is_set()
    stored = await service.get(task.id)
    assert stored is not None and stored.status == "succeeded"


async def test_shutdown_cancels_and_awaits_handlers(service: TaskService) -> None:
    task = await service.create("email")
    started, stopped = asyncio.Event(), asyncio.Event()

    async def handler(task: Task) -> None:
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    worker = Worker(service, {"email": handler})
    execution = asyncio.create_task(worker.run())
    try:
        await asyncio.wait_for(started.wait(), 2)
    finally:
        execution.cancel()
        with pytest.raises(asyncio.CancelledError):
            await execution
    assert stopped.is_set()
    assert not worker._running
    stored = await service.get(task.id)
    assert stored is not None and stored.status == "running"


async def test_concurrency_limit_does_not_preclaim_waiting_tasks(
    service: TaskService,
) -> None:
    for _ in range(3):
        await service.create("email")
    release = asyncio.Event()

    async def handler(task: Task) -> None:
        await release.wait()

    worker = Worker(service, {"email": handler}, concurrency=1)
    try:
        await worker._tick()
        await worker._tick()
        assert len(worker._running) == 1
        assert len(await service.find(status="pending")) == 2
    finally:
        release.set()
        await drain(worker)


async def test_polling_finds_work_without_feed_notifications(
    service: TaskService, monkeypatch: pytest.MonkeyPatch
) -> None:
    scanned, finished = asyncio.Event(), asyncio.Event()
    original_candidates, original_finish = service.candidates, service.finish

    async def candidates(*args, **kwargs):
        result = await original_candidates(*args, **kwargs)
        scanned.set()
        return result

    async def finish(*args, **kwargs):
        result = await original_finish(*args, **kwargs)
        finished.set()
        return result

    monkeypatch.setattr(service, "candidates", candidates)
    monkeypatch.setattr(service, "finish", finish)
    worker = Worker(
        service, {"email": AsyncMock(return_value=None)}, poll_interval=0.01
    )
    execution = asyncio.create_task(worker.run())
    try:
        async with asyncio.timeout(2):
            await scanned.wait()
            await service.create("email")
            await finished.wait()
    finally:
        execution.cancel()
        with pytest.raises(asyncio.CancelledError):
            await execution


async def test_feed_reconnects_and_resumes_last_sequence(
    service: TaskService, monkeypatch: pytest.MonkeyPatch
) -> None:
    positions: list[str] = []
    reconnected = asyncio.Event()

    async def changes(since="now"):
        positions.append(since)
        if len(positions) == 1:
            yield "42-sequence"
            raise httpx.ReadError("disconnected")
        reconnected.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(service, "changes", changes)
    worker = Worker(service, {"email": AsyncMock()}, poll_interval=0.01)
    watcher = asyncio.create_task(worker._watch())
    try:
        await asyncio.wait_for(reconnected.wait(), 2)
        assert positions == ["now", "42-sequence"]
        assert worker._wakeup.is_set()
    finally:
        watcher.cancel()
        with pytest.raises(asyncio.CancelledError):
            await watcher


@pytest.mark.parametrize("index,count", [(0, 0), (2, 2), (-1, 2), (0, 257)])
def test_invalid_partition_rejected(index: int, count: int) -> None:
    with pytest.raises(ValueError):
        Partition(index, count)


@pytest.mark.parametrize(
    "options",
    [
        {"concurrency": 0},
        {"lease": timedelta(0)},
        {"poll_interval": 0},
        {"heartbeat_interval": 0},
        {"heartbeat_interval": 600},
    ],
)
def test_invalid_worker_configuration(service: TaskService, options) -> None:
    with pytest.raises(ValueError):
        Worker(service, {"email": AsyncMock()}, **options)
