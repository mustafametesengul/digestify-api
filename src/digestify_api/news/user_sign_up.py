from digestify_api import identity
from digestify_api.infrastructure import HandledMessage, create_handled_message
from digestify_api.news.dependencies import NewsContext
from digestify_api.news.routers import message_router
from digestify_api.news.user import User, create_user, get_user, update_user


@message_router.receive(channel=identity.message_router.events)
async def handle_user_sign_up(
    context: NewsContext, event: identity.UserSignedUp
) -> None:
    database = context.database
    async with database.transaction() as connection:
        handled_message = HandledMessage(
            message_id=event.id,
            handler_name="handle_user_sign_up",
        )

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
            await create_handled_message(connection, handled_message)
            return

        if user.identity_version >= event.version:
            await create_handled_message(connection, handled_message)
            return

        user.identity_version = event.version
        user.is_deleted = False
        await update_user(connection, user)
        await create_handled_message(connection, handled_message)
