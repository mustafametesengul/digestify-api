from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from digestify_api import infrastructure
from digestify_api.identity import schemas, tokens

database = infrastructure.Database()
message_broker = infrastructure.MessageBroker()
outbox_publisher = infrastructure.OutboxRelay(
    database=database,
    message_broker=message_broker,
)
channel = infrastructure.Channel()
token_manager = tokens.TokenManager()
security = HTTPBearer()


def get_database() -> infrastructure.Database:
    return database


def get_channel() -> infrastructure.Channel:
    return channel


def get_token_manager() -> tokens.TokenManager:
    return token_manager


def get_user_claims(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> schemas.UserClaims:
    token_manager = get_token_manager()
    token = credentials.credentials
    return token_manager.decode(token, purpose=tokens.TokenPurpose.ACCESS)
