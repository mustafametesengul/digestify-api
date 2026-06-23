from datetime import date, datetime, time
from uuid import UUID

from digestify_api.infrastructure.database import (
    DocumentConflict,
    DocumentRepository,
)
from digestify_api.news.active_topics import ActiveTopics
from digestify_api.news.quota import FetchQuota
from digestify_api.news.story import Story
from digestify_api.news.topic import Topic

MAX_CONFLICT_RETRIES = 5

# Placeholder content returned until the real LLM-backed fetch lands. Each entry
# is a (title, body) template formatted with the topic so the samples at least
# look topic-specific while exercising the full scheduling/quota/persistence
# path at no cost.
_SAMPLE_STORIES: list[tuple[str, str]] = [
    (
        "{name}: what changed today",
        "A sample digest for “{name}”. This is placeholder content standing in "
        "for the real summary of {description}.",
    ),
    (
        "Three things to know about {name}",
        "Sample story two for “{name}”. Replace `generate_stories` with the "
        "model call to produce real reporting on {description}.",
    ),
    (
        "{name}: the bigger picture",
        "Sample story three for “{name}”. Until the LLM fetch is wired up, every "
        "scheduled run yields this fixed set of stories.",
    ),
]


class TopicNotActive(Exception):
    pass


async def generate_stories(topic: Topic, *, today: date) -> list[Story]:
    """Produce the latest stories for a topic.

    PLACEHOLDER — this is where the expensive, LLM-backed fetch will live.
    For now it returns a fixed set of sample stories so the surrounding
    plumbing (scheduling, quota, persistence) runs end to end with no LLM cost.
    Replace the body with a model call that maps each result onto a
    ``Story.create(...)``.
    """
    return [
        Story.create(
            topic_id=UUID(topic.id),
            title=title.format(name=topic.name, description=topic.description),
            body=body.format(name=topic.name, description=topic.description),
            language=topic.language,
            # Stagger timestamps within the day so the samples have a stable
            # newest-first order in the stories listing.
            created_at=datetime.combine(today, time(hour=9, minute=index)),
        )
        for index, (title, body) in enumerate(_SAMPLE_STORIES)
    ]


async def fetch_topic_stories(
    topic: Topic,
    *,
    today: date,
    stories: DocumentRepository[Story],
    quotas: DocumentRepository[FetchQuota],
    active_topics: DocumentRepository[ActiveTopics],
) -> list[Story]:
    """Run one story fetch for `topic` and persist the results.

    This is the single choke point every fetch flows through, so its two guards
    hold no matter who calls it:

    * the topic must be active, and
    * the owner's daily fetch budget must not be exhausted (`FetchQuotaExceeded`).

    Activeness is re-read here from the owner's `ActiveTopics` document rather
    than trusted from the caller, so a topic deactivated between a scheduler scan
    and this call does not produce a stray fetch.

    The budget is reserved *before* the expensive generation so two concurrent
    fetches can never both slip past the limit.
    """
    activation = await active_topics.get(ActiveTopics.id_for(topic.user_id))
    if activation is None or not activation.is_active(UUID(topic.id)):
        raise TopicNotActive()

    await _consume_quota(topic, today, quotas)

    generated = await generate_stories(topic, today=today)
    for story in generated:
        await stories.save(story)
    return generated


async def _consume_quota(
    topic: Topic,
    today: date,
    quotas: DocumentRepository[FetchQuota],
) -> None:
    for _ in range(MAX_CONFLICT_RETRIES):
        quota = await quotas.get(
            FetchQuota.id_for(topic.user_id)
        ) or FetchQuota.for_user(topic.user_id)
        quota.consume(today)  # raises FetchQuotaExceeded when the day is spent
        try:
            await quotas.save(quota)
            return
        except DocumentConflict:
            continue  # another fetch wrote concurrently; re-read and retry
    raise DocumentConflict(FetchQuota.id_for(topic.user_id))
