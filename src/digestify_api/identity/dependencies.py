from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from digestify_api.identity.context import Context
from digestify_api.identity.token_manager import TokenPurpose, UserClaims

security = HTTPBearer()


def get_context(request: Request) -> Context:
    return request.app.state.identity_context


def get_user_claims(
    context: Annotated[Context, Depends(get_context)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> UserClaims:
    token_manager = context.token_manager
    token = credentials.credentials
    return token_manager.decode(token, purpose=TokenPurpose.ACCESS)
