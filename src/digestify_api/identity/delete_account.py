from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import Depends

from digestify_api.identity.context import IdentityContext
from digestify_api.identity.dependencies import (
    get_context,
    get_user_claims,
    message_router,
    router,
)
from digestify_api.identity.token_manager import UserClaims
from digestify_api.identity.user import get_user, update_user
from digestify_api.infrastructure import Event, enqueue_message


class UserDeleted(Event):
    user_id: UUID
    version: int


@router.post("/delete_account")
async def delete_account(
    context: Annotated[IdentityContext, Depends(get_context)],
    user_claims: Annotated[UserClaims, Depends(get_user_claims)],
) -> None:
    async with context.database.transaction() as connection:
        now = datetime.now(timezone.utc)
        user = await get_user(connection, user_claims.id, lock=True)
        if user is None:
            return
        user.is_deleted = True
        user.updated_at = now
        user.version += 1
        user.username = None
        user.password_hash = None
        await update_user(connection, user)

        event = UserDeleted(
            user_id=user.id,
            version=user.version,
        )

        await enqueue_message(message_router.events, connection, event)
