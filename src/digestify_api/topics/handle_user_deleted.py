from digestify_api import identity
from digestify_api.topics.infrastructure import get_database, handler_registry
from digestify_api.topics.user import User, create_user, get_user, update_user


@handler_registry.event(channel=identity.channel)
async def handle_user_deleted(event: identity.UserDeleted) -> None:
    database = get_database()
    async with database.transaction() as connection:
        user = await get_user(connection, event.user_id, lock=True)
        if user is None:
            user = User(
                id=event.user_id,
                created_topics_count=0,
                active_topics_count=0,
                identity_version=event.version,
                membership_version=0,
                tier=None,
                is_deleted=True,
                created_at=event.created_at,
                updated_at=None,
            )
            await create_user(connection, user)
            return

        if user.identity_version >= event.version:
            return

        user.identity_version = event.version
        user.is_deleted = True
        await update_user(connection, user)
