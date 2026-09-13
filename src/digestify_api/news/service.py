from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from digestify_api.couchdb import Client, DocumentConflict, Repository
from digestify_api.identity.accounts import Accounts
from digestify_api.identity.token import UserClaims, UserRole
from digestify_api.news.story import Story, StoryBatch
from digestify_api.news.summarizer import Summarizer, summarize
from digestify_api.news.topic import Topic, TopicAccount, TopicDetails
from digestify_api.tasks import IntervalSchedule, LostLease, Task
from digestify_api.tasks import Service as TaskService
from digestify_api.tasks.task import utc

DATABASE_NAME = "news"
TASK_KIND = "topics.summarize"


class TopicNotFound(Exception):
    pass


class TopicLimitReached(Exception):
    pass


class RegisteredUserRequired(Exception):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


class Service:
    def __init__(
        self,
        client: Client,
        tasks: TaskService,
        *,
        summarizer: Summarizer = summarize,
        clock: Callable[[], datetime] = _now,
    ) -> None:
        self._database = client.get_database(DATABASE_NAME)
        self._accounts = Repository(TopicAccount, self._database)
        self._batches = Repository(StoryBatch, self._database)
        self._identity = Accounts(client)
        self._tasks = tasks
        self._summarizer = summarizer
        self._clock = clock

    async def init(self) -> None:
        await self._database.ensure_index(
            name="stories_by_owner_topic_day",
            fields=["type", "user_id", "topic_id", "day"],
        )

    @staticmethod
    def account_id(user_id: UUID) -> str:
        return f"topic_account:{user_id}"

    @staticmethod
    def task_id(user_id: UUID) -> str:
        return f"task:topics:{user_id}"

    async def _authorize(self, claims: UserClaims) -> None:
        if claims.role not in (UserRole.PERMANENT, UserRole.ADMIN):
            raise RegisteredUserRequired()
        await self._identity.validate_user(claims)

    async def _account(self, user_id: UUID) -> TopicAccount:
        account = await self._accounts.get(self.account_id(user_id))
        return account or TopicAccount(
            id=self.account_id(user_id), user_id=user_id
        )

    async def _update[Result](
        self, user_id: UUID, apply: Callable[[TopicAccount], Result]
    ) -> Result:
        for attempt in range(5):
            account = await self._account(user_id)
            before = account.model_dump()
            result = apply(account)
            if account.model_dump() == before:
                return result
            try:
                await self._accounts.save(account)
                return result
            except DocumentConflict:
                if attempt == 4:
                    raise
        raise AssertionError("Unreachable")

    async def _ensure_task(self, user_id: UUID) -> None:
        task_id = self.task_id(user_id)
        task = await self._tasks.get(task_id)
        if task is None:
            try:
                await self._tasks.create(
                    TASK_KIND,
                    {"user_id": str(user_id)},
                    task_id=f"topics:{user_id}",
                    partition_key=str(user_id),
                    schedule=IntervalSchedule(every=timedelta(seconds=30)),
                )
                return
            except DocumentConflict:
                task = await self._tasks.get(task_id)
        if (
            task is None
            or task.kind != TASK_KIND
            or task.payload != {"user_id": str(user_id)}
            or task.schedule is None
            or task.status not in ("pending", "running")
        ):
            raise DocumentConflict(task_id)

    async def create_topic(
        self, claims: UserClaims, details: TopicDetails
    ) -> Topic:
        await self._authorize(claims)
        await self._ensure_task(claims.id)
        now = utc(self._clock())
        topic = Topic(
            **details.model_dump(),
            id=uuid4(),
            user_id=claims.id,
            next_run_at=details.schedule.next_after(now, now),
            created_at=now,
            updated_at=now,
        )

        def apply(account: TopicAccount) -> Topic:
            for slot in account.slots:
                if slot.topic is None:
                    slot.topic = topic
                    return topic
            raise TopicLimitReached()

        return await self._update(claims.id, apply)

    async def list_topics(self, claims: UserClaims) -> list[Topic]:
        await self._authorize(claims)
        return (await self._account(claims.id)).topics()

    async def get_topic(self, claims: UserClaims, topic_id: UUID) -> Topic:
        for topic in await self.list_topics(claims):
            if topic.id == topic_id:
                return topic
        raise TopicNotFound()

    async def update_topic(
        self, claims: UserClaims, topic_id: UUID, details: TopicDetails
    ) -> Topic:
        await self._authorize(claims)

        def apply(account: TopicAccount) -> Topic:
            for slot in account.slots:
                topic = slot.topic
                if topic is not None and topic.id == topic_id:
                    now = utc(self._clock())
                    updated = Topic.model_validate(
                        {
                            **topic.model_dump(),
                            **details.model_dump(),
                            "updated_at": now,
                            "next_run_at": (
                                details.schedule.next_after(now, now)
                                if topic.schedule != details.schedule
                                else topic.next_run_at
                            ),
                        }
                    )
                    slot.topic = updated
                    return updated
            raise TopicNotFound()

        return await self._update(claims.id, apply)

    async def delete_topic(self, claims: UserClaims, topic_id: UUID) -> None:
        await self._authorize(claims)

        def apply(account: TopicAccount) -> None:
            for slot in account.slots:
                if slot.topic is not None and slot.topic.id == topic_id:
                    slot.topic = None
                    return
            raise TopicNotFound()

        await self._update(claims.id, apply)

    async def get_usage(self, claims: UserClaims) -> int:
        await self._authorize(claims)
        today = utc(self._clock()).date()
        account = await self._account(claims.id)
        return sum(
            slot.used_on is not None and slot.used_on >= today
            for slot in account.slots
        )

    async def list_stories(
        self,
        claims: UserClaims,
        topic_id: UUID,
        *,
        before: date | None = None,
        limit: int = 10,
    ) -> list[StoryBatch]:
        if not 1 <= limit <= 100:
            raise ValueError("Limit must be between 1 and 100.")
        await self.get_topic(claims, topic_id)
        batches = await self._batches.find(
            {
                "user_id": str(claims.id),
                "topic_id": str(topic_id),
                "day": {"$lt": (before or date.max).isoformat()},
            },
            sort=[
                {field: "desc"}
                for field in ("type", "user_id", "topic_id", "day")
            ],
            limit=limit,
        )
        result: list[StoryBatch] = []
        for batch in batches:
            current = await self._batches.get(batch.id)
            if current is not None:
                result.append(current)
        return result

    async def _require_claim(self, task: Task) -> None:
        current = await self._tasks.get(task.id)
        if current is None or task.claim_token is None:
            raise LostLease(task.id)
        current.require_claim(task.claim_token, utc(self._clock()))

    async def _reserve(
        self, user_id: UUID, topic_id: UUID, now: datetime
    ) -> Topic | None:
        def apply(account: TopicAccount) -> Topic | None:
            for slot in account.slots:
                topic = slot.topic
                if (
                    topic is None
                    or topic.id != topic_id
                    or topic.next_run_at > now
                ):
                    continue
                topic.next_run_at = topic.schedule.next_after(now, now)
                if slot.used_on is not None and slot.used_on >= now.date():
                    return None
                slot.used_on = now.date()
                return topic.model_copy(deep=True)
            return None

        return await self._update(user_id, apply)

    async def run(self, task: Task) -> None:
        if not isinstance(task.payload, dict):
            raise ValueError("Expected a topic task payload.")
        user_id = UUID(str(task.payload["user_id"]))
        if task.id != self.task_id(user_id) or task.kind != TASK_KIND:
            raise ValueError("Unexpected topic task identity.")
        await self._require_claim(task)
        account = await self._account(user_id)
        for candidate in account.due(utc(self._clock())):
            await self._require_claim(task)
            if not await self._identity.is_active(user_id):
                return
            now = utc(self._clock())
            day = now.date()
            topic = await self._reserve(user_id, candidate.id, now)
            if topic is None:
                continue
            await self._require_claim(task)
            current = await self._account(user_id)
            if not await self._identity.is_active(user_id) or not any(
                item.id == topic.id for item in current.topics()
            ):
                continue
            batch_id = f"stories:{topic.id}:{day}"
            drafts = await self._summarizer(topic, batch_id)
            batch = StoryBatch(
                id=batch_id,
                user_id=user_id,
                topic_id=topic.id,
                day=day,
                stories=[
                    Story(
                        **draft.model_dump(),
                        id=uuid5(NAMESPACE_URL, f"{batch_id}:{index}"),
                        topic_id=topic.id,
                        language=topic.language,
                        created_at=utc(self._clock()),
                    )
                    for index, draft in enumerate(drafts)
                ],
            )
            await self._require_claim(task)
            await self._batches.save(batch)
