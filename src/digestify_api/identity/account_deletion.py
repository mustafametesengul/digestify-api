from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends, status

from digestify_api.identity.dependencies import (
    Context,
    Unauthenticated,
    get_context,
    require_registered_user,
)
from digestify_api.identity.routers import api_router, message_router
from digestify_api.identity.token_generation import UserClaims
from digestify_api.identity.user import get_user, update_user
from digestify_api.infrastructure import Event, enqueue_message


class AccountDeleted(Event):
    user_id: UUID
    user_version: int


@api_router.post("/delete-account", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    context: Annotated[Context, Depends(get_context)],
    user_claims: Annotated[UserClaims, Depends(require_registered_user)],
) -> None:
    async with context.database.transaction() as connection:
        now = datetime.now(UTC)
        user = await get_user(connection, user_claims.id, lock=True)
        if user is None or user.is_deleted:
            raise Unauthenticated()

        user.is_deleted = True
        user.updated_at = now
        user.version += 1
        user.username = None
        user.password_hash = None
        await update_user(connection, user)

        event = AccountDeleted(user_id=user.id, user_version=user.version)
        await enqueue_message(message_router.events, connection, event)
