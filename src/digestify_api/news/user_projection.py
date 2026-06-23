import asyncio
import json
import logging
from typing import Any

import httpx

from digestify_api.infrastructure.database import (
    DocumentConflict,
    DocumentRepository,
)
from digestify_api.news.checkpoint import ProjectionCheckpoint
from digestify_api.news.user import User

logger = logging.getLogger(__name__)

CHECKPOINT_ID = "checkpoint:identity-users"
RECONNECT_DELAY_SECONDS = 5.0
HEARTBEAT_MILLISECONDS = 30_000
MAX_CONFLICT_RETRIES = 5


class UserProjection:
    """Projects `identity` users into the `news` database by tailing CouchDB's
    `_changes` feed.

    Correctness rests on two guarantees:

    * **At-least-once, never miss:** each change is applied to the news `User`
      *before* the checkpoint advances. A crash in between only replays an
      already-applied change on restart.
    * **Idempotent apply:** applying the same change twice yields the same
      result, so the replay above is harmless.

    Compaction never drops a live document from the feed, so it cannot make us
    miss a user. Only `_purge` can erase a change before we consume it — so do
    not purge identity documents ahead of this consumer.
    """

    def __init__(
        self,
        client: httpx.AsyncClient,
        users: DocumentRepository[User],
        checkpoints: DocumentRepository[ProjectionCheckpoint],
        source_database: str = "identity",
    ) -> None:
        self._client = client
        self._users = users
        self._checkpoints = checkpoints
        self._source_database = source_database

    async def run(self) -> None:
        """Consume forever, reconnecting after transient failures."""
        while True:
            try:
                await self._consume()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(
                    "user projection disconnected; reconnecting in %ss",
                    RECONNECT_DELAY_SECONDS,
                )
                await asyncio.sleep(RECONNECT_DELAY_SECONDS)

    async def _consume(self) -> None:
        checkpoint = await self._load_checkpoint()
        async with self._client.stream(
            "POST",
            f"/{self._source_database}/_changes",
            params={
                "feed": "continuous",
                "since": checkpoint.last_seq,
                "include_docs": "true",
                "filter": "_selector",
                "heartbeat": str(HEARTBEAT_MILLISECONDS),
            },
            json={"selector": {"type": "user"}},
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.strip():
                    continue  # heartbeat keep-alive
                await self._apply_line(line, checkpoint)

    async def _apply_line(self, line: str, checkpoint: ProjectionCheckpoint) -> None:
        change: dict[str, Any] = json.loads(line)
        # The final row of a closing feed is {"last_seq": ...} with no "id".
        if "id" not in change or "seq" not in change:
            return

        await self._apply_change(change)

        # Advance the checkpoint only after the change is durably applied.
        checkpoint.last_seq = change["seq"]
        await self._save_checkpoint(checkpoint)

    async def _apply_change(self, change: dict[str, Any]) -> None:
        doc = change.get("doc") or {}
        is_deleted = bool(
            change.get("deleted") or doc.get("_deleted") or doc.get("is_deleted")
        )
        await self._upsert(User(id=change["id"], is_deleted=is_deleted))

    async def _upsert(self, user: User) -> None:
        for _ in range(MAX_CONFLICT_RETRIES):
            existing = await self._users.get(user.id)
            user.rev = existing.rev if existing is not None else None
            try:
                await self._users.save(user)
                return
            except DocumentConflict:
                continue  # someone else wrote concurrently; re-read and retry
        raise DocumentConflict(user.id)

    async def _load_checkpoint(self) -> ProjectionCheckpoint:
        checkpoint = await self._checkpoints.get(CHECKPOINT_ID)
        if checkpoint is None:
            checkpoint = ProjectionCheckpoint.start(CHECKPOINT_ID)
        return checkpoint

    async def _save_checkpoint(self, checkpoint: ProjectionCheckpoint) -> None:
        await self._checkpoints.save(checkpoint)
