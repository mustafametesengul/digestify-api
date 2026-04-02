from digestify_api import identity
from digestify_api.infrastructure.handled_message import (
    HandledMessage,
    create_handled_message,
    has_message_been_handled,
)
from digestify_api.news.dependencies import Context
from digestify_api.news.routers import message_router
from digestify_api.news.user import get_user, update_user


@message_router.receive(channel=identity.message_router.events)
async def on_user_deletion(context: Context, event: identity.AccountDeleted) -> None:
    database = context.database
    async with database.transaction() as connection:
        if await has_message_been_handled(connection, event.id, "on_user_deletion"):
            return

        handled_message = HandledMessage(
            message_id=event.id,
            handler_name="on_user_deletion",
        )

        user = await get_user(connection, event.user_id, lock=True)
        if user is None or user.is_deleted:
            raise Exception("User not found or already deleted")

        user.is_deleted = True
        await update_user(connection, user)
        await create_handled_message(connection, handled_message)
