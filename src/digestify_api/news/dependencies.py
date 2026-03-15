from fastapi import APIRouter, Request

from digestify_api.infrastructure import MessageRouter
from digestify_api.news.context import Context

router = APIRouter()
message_router = MessageRouter()


def get_context(request: Request) -> Context:
    return request.app.state.news_context
