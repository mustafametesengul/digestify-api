from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import Depends

from digestify_api.identity.dependencies import (
    Context,
    get_context,
    get_user_claims,
)
from digestify_api.identity.routers import api_router, message_router
from digestify_api.identity.token_generation import UserClaims
from digestify_api.identity.user import get_user, update_user
from digestify_api.infrastructure import Event, enqueue_message


class AccountDeleted(Event):
    user_id: UUID
    version: int


@api_router.post("/delete-account")
async def delete_account(
    context: Annotated[Context, Depends(get_context)],
    user_claims: Annotated[UserClaims, Depends(get_user_claims)],
) -> None:
    async with context.database.transaction() as connection:
        now = datetime.now(timezone.utc)
        user = await get_user(connection, user_claims.id, lock=True)
        if user is None or user.is_deleted:
            return
        user.is_deleted = True
        user.updated_at = now
        user.version += 1
        user.username = None
        user.password_hash = None
        await update_user(connection, user)

        event = AccountDeleted(user_id=user.id, version=user.version)
        await enqueue_message(message_router.events, connection, event)
