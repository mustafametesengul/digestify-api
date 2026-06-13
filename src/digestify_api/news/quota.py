from datetime import date
from typing import Literal, Self
from uuid import UUID

from digestify_api.infrastructure.couchdb import Document

# A user may trigger at most this many (expensive, LLM-backed) story fetches per
# local day. Every fetch path — scheduled or otherwise — consumes from this one
# budget, so a user can never cause more than this many fetches in a day no
# matter how they toggle topics or rewrite schedules.
DAILY_FETCH_LIMIT = 5


class FetchQuotaExceeded(Exception):
    pass


class FetchQuota(Document):
    """Per-user daily story-fetch budget.

    The window is a calendar date rather than a rolling timestamp so the budget
    is trivial to reason about and resets cleanly each day. The date is whatever
    the caller supplies (typically the topic's local "today"); callers should be
    consistent about which zone they pass.
    """

    type: Literal["fetch_quota"] = "fetch_quota"
    window: date | None = None
    count: int = 0

    @staticmethod
    def id_for(user_id: UUID) -> str:
        return f"fetch_quota:{user_id}"

    @classmethod
    def for_user(cls, user_id: UUID) -> Self:
        return cls(id=cls.id_for(user_id))

    def consume(self, today: date) -> None:
        """Spend one unit of today's budget, or raise if it is exhausted."""
        if self.window != today:
            self.window = today
            self.count = 0
        if self.count >= DAILY_FETCH_LIMIT:
            raise FetchQuotaExceeded()
        self.count += 1
