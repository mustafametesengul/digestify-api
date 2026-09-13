import asyncio
from datetime import timedelta
from uuid import uuid4

import jwt
import pytest

from digestify_api.couchdb import (
    Repository,
    UnresolvedDocumentConflict,
    WriteNotConfirmed,
)
from digestify_api.identity.token import UserRole
from digestify_api.identity.user import User
from digestify_api.news.service import (
    RegisteredUserRequired,
    TopicLimitReached,
    TopicNotFound,
)
from digestify_api.news.topic import TopicDetails
from tests.news.conftest import Context


async def test_crud_and_owner_isolation(context: Context, details):
    topic = await context.service.create_topic(context.claims, details)
    assert await context.service.list_topics(context.claims) == [topic]
    changed = details.model_copy(update={"name": "Updated"})
    updated = await context.service.update_topic(
        context.claims, topic.id, changed
    )
    assert updated.name == "Updated"
    assert updated.next_run_at == topic.next_run_at
    with pytest.raises(TopicNotFound):
        await context.service.get_topic(context.claims, uuid4())
    await context.service.delete_topic(context.claims, topic.id)
    assert await context.service.list_topics(context.claims) == []


@pytest.mark.parametrize("role", [UserRole.PERMANENT, UserRole.ADMIN])
async def test_five_topic_limit(context: Context, details, role):
    context.claims.role = role
    for _ in range(5):
        await context.service.create_topic(context.claims, details)
    with pytest.raises(TopicLimitReached):
        await context.service.create_topic(context.claims, details)
    assert len(await context.tasks.find()) == 1


async def test_concurrent_creation_cannot_exceed_limit(context, details):
    for _ in range(4):
        await context.service.create_topic(context.claims, details)
    results = await asyncio.gather(
        context.service.create_topic(context.claims, details),
        context.service.create_topic(context.claims, details),
        return_exceptions=True,
    )
    assert (
        sum(isinstance(result, TopicLimitReached) for result in results) == 1
    )
    assert len(await context.service.list_topics(context.claims)) == 5


async def test_anonymous_and_deleted_accounts_cannot_create(context, details):
    context.claims.role = UserRole.ANONYMOUS
    with pytest.raises(RegisteredUserRequired):
        await context.service.create_topic(context.claims, details)
    context.claims.role = UserRole.PERMANENT
    user = await context.users.get(str(context.claims.id))
    user.delete()
    await context.users.save(user)
    with pytest.raises(jwt.InvalidTokenError):
        await context.service.create_topic(context.claims, details)


async def test_due_summarization_stores_multiple_stories(context, details):
    topic = await context.service.create_topic(context.claims, details)
    await context.run()
    assert context.summarizer.calls == []
    context.clock.now = topic.next_run_at
    await context.run()
    assert len(context.summarizer.calls) == 1
    batches = await context.service.list_stories(context.claims, topic.id)
    assert len(batches) == 1
    assert len(batches[0].stories) == 2
    assert await context.service.get_usage(context.claims) == 1


async def test_schedule_edits_do_not_reset_daily_usage(context, details):
    topic = await context.service.create_topic(context.claims, details)
    context.clock.now = topic.next_run_at
    await context.run()
    for hour in (10, 11, 12):
        changed = TopicDetails.model_validate(
            {
                **details.model_dump(),
                "schedule": {"time": f"{hour}:00", "timezone": "UTC"},
            }
        )
        topic = await context.service.update_topic(
            context.claims, topic.id, changed
        )
        context.clock.now = topic.next_run_at
        await context.run()
    assert len(context.summarizer.calls) == 1
    context.clock.now += timedelta(days=1)
    await context.run()
    assert len(context.summarizer.calls) == 2


async def test_delete_recreate_does_not_reset_any_slots(context, details):
    topics = [
        await context.service.create_topic(context.claims, details)
        for _ in range(5)
    ]
    context.clock.now = topics[0].next_run_at
    await context.run()
    assert len(context.summarizer.calls) == 5
    for topic in topics:
        await context.service.delete_topic(context.claims, topic.id)
    changed = details.model_dump()
    changed["schedule"] = {"time": "10:00", "timezone": "UTC"}
    replacements = [
        await context.service.create_topic(
            context.claims, TopicDetails.model_validate(changed)
        )
        for _ in range(5)
    ]
    context.clock.now = replacements[0].next_run_at
    await context.run()
    assert len(context.summarizer.calls) == 5
    assert await context.service.get_usage(context.claims) == 5
    context.clock.now += timedelta(days=1)
    await context.run()
    assert len(context.summarizer.calls) == 10


async def test_ai_failure_consumes_reservation(context, details):
    topic = await context.service.create_topic(context.claims, details)
    context.clock.now = topic.next_run_at
    context.summarizer.error = RuntimeError("Provider failed")
    with pytest.raises(RuntimeError, match="Provider failed"):
        await context.run()
    context.clock.now += timedelta(minutes=1)
    await context.run()
    assert len(context.summarizer.calls) == 1
    assert await context.service.list_stories(context.claims, topic.id) == []


async def test_deleted_account_stops_ai(context, details):
    topic = await context.service.create_topic(context.claims, details)
    user = await context.users.get(str(context.claims.id))
    user.delete()
    await context.users.save(user)
    context.clock.now = topic.next_run_at
    await context.run()
    assert context.summarizer.calls == []


async def test_visible_conflicts_block_ai(context, details):
    topic = await context.service.create_topic(context.claims, details)
    context.clock.now = topic.next_run_at
    identity = context.service.account_id(context.claims.id)
    context.couch.databases["news"][identity]["_conflicts"] = ["2-divergent"]
    with pytest.raises(UnresolvedDocumentConflict):
        await context.run()
    assert context.summarizer.calls == []


async def test_unconfirmed_reservation_never_calls_ai(context, details):
    topic = await context.service.create_topic(context.claims, details)
    context.clock.now = topic.next_run_at
    task = await context.tasks.claim(
        context.service.task_id(context.claims.id),
        "worker",
        timedelta(minutes=10),
    )
    context.couch.next_write_status = 202
    with pytest.raises(WriteNotConfirmed):
        await context.service.run(task)
    assert context.summarizer.calls == []
    assert await context.service.get_usage(context.claims) == 1
    await context.service.run(task)
    assert context.summarizer.calls == []


async def test_news_documents_cannot_override_identity_state(context, details):
    user = await context.users.get(str(context.claims.id))
    assert user is not None
    shadow = user.model_copy(update={"rev": None})
    await Repository(User, context.client.get_database("news")).save(shadow)
    user.delete()
    await context.users.save(user)
    with pytest.raises(jwt.InvalidTokenError):
        await context.service.create_topic(context.claims, details)
    assert context.summarizer.calls == []


async def test_identity_conflict_blocks_summarization(context, details):
    topic = await context.service.create_topic(context.claims, details)
    context.clock.now = topic.next_run_at
    context.couch.databases["identity"][str(context.claims.id)][
        "_conflicts"
    ] = ["2-divergent"]
    with pytest.raises(UnresolvedDocumentConflict):
        await context.run()
    assert context.summarizer.calls == []
