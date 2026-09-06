import asyncio
from datetime import timedelta

import httpx
import pytest

from digestify_api.couchdb import Database, UnresolvedDocumentConflict
from digestify_api.tasks import Partition, Task, TaskService, Worker
from tests.couchdb.test_integration import client as client
from tests.couchdb.test_integration import database as database
from tests.couchdb.test_integration import pytestmark as pytestmark
from tests.task.conftest import Clock


@pytest.fixture
async def service(database: Database, clock: Clock) -> TaskService:
    service = TaskService(database, clock=clock)
    await service.init()
    return service


async def test_live_competing_claims(service: TaskService) -> None:
    task = await service.create("example")
    claims = await asyncio.gather(
        service.claim(task.id, "first", timedelta(minutes=1)),
        service.claim(task.id, "second", timedelta(minutes=1)),
    )
    assert sum(claim is not None for claim in claims) == 1
    winner = next(claim for claim in claims if claim is not None)
    assert winner.claim_token is not None
    finished = await service.finish(task.id, winner.claim_token, result={"done": True})
    assert finished.status == "succeeded"
    assert await service.get(task.id) == finished


async def test_live_indexed_query_and_partitioned_execution(
    service: TaskService, clock: Clock
) -> None:
    created = [
        await service.create("example", partition_key=f"user:{number}")
        for number in range(8)
    ]
    await service.create("example", scheduled_at=clock.now + timedelta(hours=1))
    seen: list[tuple[int, Task]] = []

    async def first(task: Task) -> None:
        seen.append((0, task))

    async def second(task: Task) -> None:
        seen.append((1, task))

    for index, handler in enumerate((first, second)):
        worker = Worker(service, {"example": handler}, partition=Partition(index, 2))
        await worker._tick()
        async with asyncio.timeout(15):
            await asyncio.gather(*list(worker._running.values()))
    assert {task.id for _, task in seen} == {task.id for task in created}
    assert len(seen) == len(created)
    assert all(Partition(index, 2).owns(task.partition_key) for index, task in seen)
    assert len(await service.find(status="succeeded")) == 8


async def test_live_changes_feed(service: TaskService) -> None:
    await service.create("example")
    feed = service.changes("0")
    try:
        async with asyncio.timeout(15):
            sequence = await anext(feed)
        assert sequence and sequence != "0"
    finally:
        await feed.aclose()


async def test_live_divergent_revisions_block_execution(
    service: TaskService, database: Database, client: httpx.AsyncClient
) -> None:
    task = await service.create("example")
    document = await database.get(task.id)
    assert document is not None and task.rev is not None
    root = task.rev.split("-", 1)[1]
    branches = [
        {
            **document,
            "_rev": f"2-{revision}",
            "_revisions": {"start": 2, "ids": [revision, root]},
        }
        for revision in ("a" * 32, "b" * 32)
    ]
    response = await client.post(
        f"/{database.name}/_bulk_docs", json={"new_edits": False, "docs": branches}
    )
    response.raise_for_status()
    with pytest.raises(UnresolvedDocumentConflict):
        await service.claim(task.id, "worker", timedelta(minutes=1))


async def test_live_cancellation_stops_handler(service: TaskService) -> None:
    task = await service.create("example")
    started, stopped = asyncio.Event(), asyncio.Event()

    async def handler(task: Task) -> None:
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    worker = Worker(service, {"example": handler}, heartbeat_interval=0.05)
    await worker._tick()
    executions = list(worker._running.values())
    try:
        async with asyncio.timeout(15):
            await started.wait()
            await service.cancel(task.id)
            await stopped.wait()
            await asyncio.gather(*executions)
        stored = await service.get(task.id)
        assert stored is not None and stored.status == "cancelled"
    finally:
        for execution in executions:
            execution.cancel()
        await asyncio.gather(*executions, return_exceptions=True)
