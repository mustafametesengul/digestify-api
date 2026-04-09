from digestify_api import identity
from digestify_api.infrastructure import (
    HandledMessage,
    create_handled_message,
    has_message_been_handled,
)
from digestify_api.news.dependencies import Context
from digestify_api.news.routers import message_router
from digestify_api.news.user import User, create_user


@message_router.receive(channel=identity.message_router.events)
async def on_user_sign_up(context: Context, event: identity.UserSignedUp) -> None:
    database = context.database
    async with database.transaction() as connection:
        if await has_message_been_handled(connection, event.id, "on_user_sign_up"):
            return

        handled_message = HandledMessage(
            message_id=event.id,
            handler_name="on_user_sign_up",
        )

        user = User(
            id=event.user_id,
            reserved_topics_count=0,
            active_topics_count=0,
            is_deleted=False,
        )
        await create_user(connection, user)
        await create_handled_message(connection, handled_message)
