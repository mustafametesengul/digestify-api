from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from digestify_api.identity import TokenDecoder, UserClaims
from digestify_api.infrastructure import Database, MessageBroker, OutboxRelay


@dataclass
class Context:
    database: Database
    message_broker: MessageBroker
    outbox_relay: OutboxRelay
    token_decoder: TokenDecoder


def get_context(request: Request) -> Context:
    return request.app.state.news_context


security = HTTPBearer()


def get_user_claims(
    context: Annotated[Context, Depends(get_context)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> UserClaims:
    token = credentials.credentials
    return context.token_decoder.decode(token)
