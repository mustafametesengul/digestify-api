from fastapi import APIRouter

from digestify_api.infrastructure import MessageRouter

api_router = APIRouter()
message_router = MessageRouter()
