from typing import Literal, Self
from uuid import UUID

from digestify_api.infrastructure.couchdb import Document

# A user may have at most this many topics active at once. Each active topic
# costs one scheduled (LLM-backed) fetch per day, so this also bounds a user's
# daily scheduled spend — see `digestify_api.news.quota`.
MAX_ACTIVE_TOPICS = 5


class ActiveTopicLimitExceeded(Exception):
    pass


class ActiveTopics(Document):
    """The set of a user's currently active topics, held in one document.

    Keeping the whole set in a single document is what makes the
    `MAX_ACTIVE_TOPICS` cap enforceable at the ACID level: an activation reads
    this document, checks the cap, and writes it back under its revision. Two
    concurrent activations therefore serialise — the second loses the optimistic
    write, re-reads the now-fuller set, and re-checks the cap — so the limit can
    never be exceeded no matter how the activations interleave.
    """

    type: Literal["active_topics"] = "active_topics"
    user_id: UUID
    topic_ids: list[UUID] = []

    @staticmethod
    def id_for(user_id: UUID) -> str:
        return f"active_topics:{user_id}"

    @classmethod
    def for_user(cls, user_id: UUID) -> Self:
        return cls(id=cls.id_for(user_id), user_id=user_id)

    def is_active(self, topic_id: UUID) -> bool:
        return topic_id in self.topic_ids

    def activate(self, topic_id: UUID) -> None:
        """Add `topic_id` to the active set, or raise if that would exceed the
        cap. Activating an already-active topic is a no-op."""
        if topic_id in self.topic_ids:
            return
        if len(self.topic_ids) >= MAX_ACTIVE_TOPICS:
            raise ActiveTopicLimitExceeded()
        self.topic_ids.append(topic_id)

    def deactivate(self, topic_id: UUID) -> None:
        """Remove `topic_id` from the active set; a no-op if it was not active."""
        if topic_id in self.topic_ids:
            self.topic_ids.remove(topic_id)
