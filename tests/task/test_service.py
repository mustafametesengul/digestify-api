import asyncio
from datetime import time, timedelta

import pytest

from digestify_api.couchdb import (
    DocumentConflict,
    UnresolvedDocumentConflict,
    WriteNotConfirmed,
)
from digestify_api.tasks import DailySchedule, LostLease, Partition, TaskService
from tests.task.conftest import Clock, InMemoryCouch

LEASE = timedelta(minutes=1)


async def test_create_get_find_and_cancel(service: TaskService, clock: Clock) -> None:
    await service.init()
    task = await service.create("email", {"subject": "hello"}, partition_key="user:1")
    assert await service.get(task.id) == task
    assert await service.find(partition_key="user:1", status="pending") == [task]
    assert await service.find(partition_key="user:other") == []
    cancelled = await service.cancel(task.id)
    assert cancelled is not None and cancelled.status == "cancelled"
    assert await service.cancel(task.id) == cancelled
    assert await service.claim(task.id, "worker", LEASE) is None
    assert await service.get("missing") is None
    assert await service.cancel("missing") is None


async def test_explicit_id_prevents_duplicate_creation(service: TaskService) -> None:
    await service.create("email", task_id="delivery:1")
    with pytest.raises(DocumentConflict):
        await service.create("email", task_id="delivery:1")


async def test_daily_first_run_is_next_local_occurrence(
    service: TaskService, clock: Clock
) -> None:
    task = await service.create(
        "email", schedule=DailySchedule(time=time(12), timezone="UTC")
    )
    assert task.scheduled_at == clock.now + timedelta(hours=12)


async def test_competing_claims_run_only_one_worker(
    service: TaskService, couch: InMemoryCouch
) -> None:
    task = await service.create("email")
    couch.read_barrier = asyncio.Barrier(2)
    async with asyncio.timeout(2):
        claims = await asyncio.gather(
            service.claim(task.id, "first", LEASE),
            service.claim(task.id, "second", LEASE),
        )
    assert sum(claim is not None for claim in claims) == 1
    stored = await service.get(task.id)
    assert stored is not None and stored.attempts == 1


async def test_stale_completion_cannot_overwrite_reclaim(
    service: TaskService, clock: Clock
) -> None:
    task = await service.create("email")
    first = await service.claim(task.id, "first", LEASE)
    assert first is not None and first.claim_token is not None
    clock.now += LEASE
    second = await service.claim(task.id, "second", LEASE)
    assert second is not None
    with pytest.raises(LostLease):
        await service.finish(task.id, first.claim_token)
    assert await service.get(task.id) == second


async def test_renew_and_complete_persist_result(
    service: TaskService, clock: Clock
) -> None:
    task = await service.create("email")
    claimed = await service.claim(task.id, "worker", LEASE)
    assert claimed is not None and claimed.claim_token is not None
    clock.now += timedelta(seconds=30)
    renewed = await service.renew(task.id, claimed.claim_token, LEASE)
    assert renewed.lease_until == clock.now + LEASE
    finished = await service.finish(task.id, claimed.claim_token, result={"sent": True})
    assert finished.status == "succeeded"
    assert finished.last_result == {"sent": True}
    assert await service.get(task.id) == finished


async def test_visible_conflicts_block_claims(
    service: TaskService, couch: InMemoryCouch
) -> None:
    task = await service.create("email")
    couch.docs[task.id]["_conflicts"] = ["2-diverged"]
    with pytest.raises(UnresolvedDocumentConflict):
        await service.claim(task.id, "worker", LEASE)
    assert couch.docs[task.id]["status"] == "pending"


async def test_unconfirmed_claim_may_commit_but_is_not_returned(
    service: TaskService, couch: InMemoryCouch
) -> None:
    task = await service.create("email")
    couch.next_write_status = 202
    with pytest.raises(WriteNotConfirmed):
        await service.claim(task.id, "worker", LEASE)
    stored = await service.get(task.id)
    assert stored is not None and stored.status == "running"


async def test_candidates_select_only_due_owned_registered_tasks(
    service: TaskService, clock: Clock
) -> None:
    keys = [str(number) for number in range(30)]
    partition = Partition(0, 2)
    owned_key = next(key for key in keys if partition.owns(key))
    other_key = next(key for key in keys if not partition.owns(key))
    due = await service.create("email", partition_key=owned_key)
    await service.create("email", partition_key=other_key)
    await service.create("other", partition_key=owned_key)
    await service.create(
        "email", partition_key=owned_key, scheduled_at=clock.now + LEASE
    )
    assert await service.candidates(partition.buckets, ["email"]) == [due]
    await service.claim(due.id, "worker", LEASE)
    assert await service.candidates(partition.buckets, ["email"]) == []
    clock.now += LEASE
    candidates = await service.candidates(partition.buckets, ["email"])
    assert due.id in [task.id for task in candidates]


async def test_deadline_strings_sort_with_subsecond_precision(
    service: TaskService, clock: Clock
) -> None:
    due = await service.create("email")
    await service.create("email", scheduled_at=clock.now + timedelta(microseconds=2))
    clock.now += timedelta(microseconds=1)
    assert await service.candidates(Partition().buckets, ["email"]) == [due]


async def test_expired_final_attempt_persists_failure(
    service: TaskService, clock: Clock
) -> None:
    task = await service.create("email", max_attempts=1)
    await service.claim(task.id, "worker", LEASE)
    clock.now += LEASE
    assert await service.claim(task.id, "replacement", LEASE) is None
    stored = await service.get(task.id)
    assert stored is not None and stored.status == "failed"


async def test_unconfirmed_create_can_be_checked_by_stable_id(
    service: TaskService, couch: InMemoryCouch
) -> None:
    couch.next_write_status = 202
    with pytest.raises(WriteNotConfirmed):
        await service.create("email", task_id="stable")
    assert await service.get("task:stable") is not None
