from fastapi import APIRouter

from digestify_api.infrastructure import MessageRouter

router = APIRouter()
message_router = MessageRouter()
