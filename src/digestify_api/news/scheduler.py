import asyncio
import logging
from datetime import UTC, datetime

from digestify_api.infrastructure.database import (
    DocumentConflict,
    DocumentRepository,
)
from digestify_api.news.active_topics import ActiveTopics
from digestify_api.news.fetch import TopicNotActive, fetch_topic_stories
from digestify_api.news.quota import FetchQuota, FetchQuotaExceeded
from digestify_api.news.story import Story
from digestify_api.news.topic import Topic

logger = logging.getLogger(__name__)

TICK_SECONDS = 5.0
# Each tick reads the active topics in one Mango query. This bounds how many it
# will consider; well above any realistic active-topic count for now. If the
# active set ever approaches this, switch the scan to bookmark pagination.
SCAN_LIMIT = 1000


class TopicScheduler:
    """Fetches stories for active topics when their daily schedule comes due.

    The scheduler holds no state of its own: a topic's `last_execution_date`
    *is* the schedule, so the loop survives restarts and resumes mid-day with no
    catch-up logic. Running it on several replicas is safe — each due topic is
    claimed with an optimistic write before any fetch, so exactly one replica
    does the (expensive) work.
    """

    def __init__(
        self,
        topics: DocumentRepository[Topic],
        stories: DocumentRepository[Story],
        quotas: DocumentRepository[FetchQuota],
        active_topics: DocumentRepository[ActiveTopics],
        tick_seconds: float = TICK_SECONDS,
    ) -> None:
        self._topics = topics
        self._stories = stories
        self._quotas = quotas
        self._active_topics = active_topics
        self._tick_seconds = tick_seconds

    async def run(self) -> None:
        """Tick forever, surviving transient failures."""
        while True:
            try:
                await self._tick(datetime.now(UTC))
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("scheduler tick failed")
            await asyncio.sleep(self._tick_seconds)

    async def _tick(self, now: datetime) -> None:
        # Activeness now lives per user in `ActiveTopics`, so the set of active
        # topics is the union of every user's set. Scan those documents, then
        # load just the referenced topics in one query.
        activations = await self._active_topics.find(
            {"type": "active_topics"},
            limit=SCAN_LIMIT,
        )
        topic_ids = {str(topic_id) for doc in activations for topic_id in doc.topic_ids}
        if not topic_ids:
            return

        topics = await self._topics.find(
            {"type": "topic", "_id": {"$in": sorted(topic_ids)}},
            limit=SCAN_LIMIT,
        )
        for topic in topics:
            if topic.is_due(now):
                await self._run_topic(topic, now)

    async def _run_topic(self, topic: Topic, now: datetime) -> None:
        today = topic.local_date(now)

        # Claim today *before* fetching so a crash or a second replica cannot
        # double-spend on the same topic. The trade-off is that a transient
        # generation failure forfeits this topic's run until tomorrow rather
        # than risk a duplicate (expensive) fetch.
        topic.mark_executed(now)
        try:
            await self._topics.save(topic)
        except DocumentConflict:
            return  # another writer changed this topic; reconsider next tick

        try:
            await fetch_topic_stories(
                topic,
                today=today,
                stories=self._stories,
                quotas=self._quotas,
                active_topics=self._active_topics,
            )
        except FetchQuotaExceeded:
            logger.info(
                "daily fetch budget exhausted for user %s; skipping topic %s",
                topic.user_id,
                topic.id,
            )
        except TopicNotActive:
            # Deactivated between the scan and now; nothing to do.
            pass
