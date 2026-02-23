from digestify_api import identity
from digestify_api.infrastructure import HandlerRegistry
from digestify_api.stories import dependencies

handler_registry = HandlerRegistry(
    channel=dependencies.channel,
    database=dependencies.database,
)


@handler_registry.event(channel=identity.channel)
async def handle_story_event(event: identity.UserSignedUp) -> None:
    print(f"Received event: {event}")
