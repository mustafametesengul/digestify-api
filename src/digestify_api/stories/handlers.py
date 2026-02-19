from digestify_api.auth import UserSignedUp
from digestify_api.messaging import HandlerRegistry

handler_registry = HandlerRegistry(service_name="stories")


@handler_registry.event(service_name="auth")
async def handle_story_event(event: UserSignedUp) -> None:
    print(f"Received event: {event}")
