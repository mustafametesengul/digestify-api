import uuid
from datetime import datetime, timezone

import pytest

from digestify_api.models import TaskCreate, TaskStatus
from digestify_api.repositories.task_repository import TaskRepository


@pytest.mark.asyncio
async def test_create_and_read_task(task_repo: TaskRepository):
    task_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    task_create = TaskCreate(
        id=task_id,
        type="email_digest",
        payload='{"user_id": "123", "content": "digest"}',
        scheduled_at=now,
        status=TaskStatus.PENDING,
    )

    await task_repo.create_task(task_create)

    task_read = await task_repo.read_task(task_id)
    assert task_read is not None
    assert task_read.id == task_id
    assert task_read.type == "email_digest"
    assert task_read.payload == '{"user_id": "123", "content": "digest"}'
    assert task_read.status == TaskStatus.PENDING
    # Basic check ensuring timestamps are populated
    assert task_read.created_at is not None
    assert task_read.updated_at is not None


@pytest.mark.asyncio
async def test_read_non_existent_task(task_repo: TaskRepository):
    task_id = uuid.uuid4()
    task_read = await task_repo.read_task(task_id)
    assert task_read is None


@pytest.mark.asyncio
async def test_update_task_status(task_repo: TaskRepository):
    task_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    task_create = TaskCreate(
        id=task_id,
        type="cleanup",
        payload="{}",
        scheduled_at=now,
        status=TaskStatus.PENDING,
    )

    await task_repo.create_task(task_create)

    # Update to IN_PROGRESS
    await task_repo.update_task_status(task_id, TaskStatus.IN_PROGRESS)
    task_read = await task_repo.read_task(task_id)
    assert task_read is not None
    assert task_read.status == TaskStatus.IN_PROGRESS

    # Update to COMPLETED
    await task_repo.update_task_status(task_id, TaskStatus.COMPLETED)
    task_read = await task_repo.read_task(task_id)
    assert task_read is not None
    assert task_read.status == TaskStatus.COMPLETED
