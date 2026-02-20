from digestify_api import identity
from digestify_api.identity import UserSignedUp
from digestify_api.infrastructure.handler_registry import HandlerRegistry
from digestify_api.stories.dependencies import channel

handler_registry = HandlerRegistry(channel=channel)


@handler_registry.event(channel=identity.channel)
async def handle_story_event(event: UserSignedUp) -> None:
    print(f"Received event: {event}")
