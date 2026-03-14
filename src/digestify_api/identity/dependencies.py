from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from digestify_api.identity.context import IdentityContext
from digestify_api.identity.token_manager import TokenPurpose, UserClaims
from digestify_api.infrastructure import MessageRouter

router = APIRouter()
message_router = MessageRouter()


def get_context(request: Request) -> IdentityContext:
    return request.app.state.identity_context


security = HTTPBearer()


def get_user_claims(
    context: Annotated[IdentityContext, Depends(get_context)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> UserClaims:
    token_manager = context.token_manager
    token = credentials.credentials
    return token_manager.decode(token, purpose=TokenPurpose.ACCESS)
