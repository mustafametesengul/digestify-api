from digestify_api import identity
from digestify_api.news.context import Context
from digestify_api.news.dependencies import message_router
from digestify_api.news.user import User, create_user, get_user, update_user


@message_router.receive(channel=identity.message_router.events)
async def handle_user_signed_up(context: Context, event: identity.UserSignedUp) -> None:
    database = context.database
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
                is_deleted=False,
                created_at=event.created_at,
                updated_at=None,
            )
            await create_user(connection, user)
            return

        if user.identity_version >= event.version:
            return

        user.identity_version = event.version
        user.is_deleted = False
        await update_user(connection, user)
