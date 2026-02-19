from digestify_api.identity import UserSignedUp
from digestify_api.infrastructure import HandlerRegistry

handler_registry = HandlerRegistry(service_name="stories")


@handler_registry.event(service_name="auth")
async def handle_story_event(event: UserSignedUp) -> None:
    print(f"Received event: {event}")
