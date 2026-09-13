from collections.abc import Awaitable, Callable

from digestify_api.news.story import StoryDraft
from digestify_api.news.topic import Topic

Summarizer = Callable[[Topic, str], Awaitable[list[StoryDraft]]]


async def summarize(topic: Topic, idempotency_key: str) -> list[StoryDraft]:
    """Replace with an async provider using the supplied idempotency key."""
    return [
        StoryDraft(
            title=f"{topic.name}: daily briefing",
            body=f"Mock summary for: {topic.description}",
        ),
        StoryDraft(
            title=f"{topic.name}: further reading",
            body="Mock follow-up story. No external AI service was called.",
        ),
    ]
