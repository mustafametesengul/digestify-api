from digestify_api import identity
from digestify_api.infrastructure import HandlerRegistry
from digestify_api.topics import dependencies, queries, schemas

handler_registry = HandlerRegistry(
    channel=dependencies.channel,
    database=dependencies.database,
)


@handler_registry.event(channel=identity.channel)
async def handle_user_signed_up(event: identity.UserSignedUp) -> None:
    database = dependencies.get_database()
    async with database.transaction():
        user = await queries.get_user(database, event.user_id, lock=True)
        if user is None:
            user = queries.User(
                id=event.user_id,
                created_topics_count=0,
                identity_version=event.version,
                membership_version=0,
                tier=None,
                is_deleted=False,
            )
            await queries.create_user(database, user)
            return

        if user.identity_version >= event.version:
            return

        user.identity_version = event.version
        user.is_deleted = False
        await queries.update_user(database, user)


@handler_registry.event(channel=identity.channel)
async def handle_user_deleted(event: identity.UserDeleted) -> None:
    database = dependencies.get_database()
    async with database.transaction():
        user = await queries.get_user(database, event.user_id, lock=True)
        if user is None:
            user = schemas.User(
                id=event.user_id,
                created_topics_count=0,
                identity_version=event.version,
                membership_version=0,
                tier="",
                is_deleted=True,
            )
            await queries.create_user(database, user)
            return

        if user.identity_version >= event.version:
            return

        user.identity_version = event.version
        user.is_deleted = True
        await queries.update_user(database, user)
