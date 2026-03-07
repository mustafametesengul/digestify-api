from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import Depends

from digestify_api.identity.bootstrap import get_channel, get_database, router
from digestify_api.identity.tokens import UserClaims, get_user_claims
from digestify_api.identity.user import get_user, update_user
from digestify_api.infrastructure import Channel, Database, Event


class UserDeleted(Event):
    user_id: UUID
    version: int


@router.post("/delete_account")
async def delete_account(
    database: Annotated[Database, Depends(get_database)],
    channel: Annotated[Channel, Depends(get_channel)],
    user_claims: Annotated[UserClaims, Depends(get_user_claims)],
) -> None:
    async with database.transaction() as connection:
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

        await channel.save_event(connection, event)
