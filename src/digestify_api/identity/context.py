from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from digestify_api.identity.token_decoder import TokenDecoder
from digestify_api.identity.token_generator import TokenGenerator, UserClaims
from digestify_api.infrastructure import Database


@dataclass
class Context:
    database: Database
    token_generator: TokenGenerator
    token_decoder: TokenDecoder


def get_context(request: Request) -> Context:
    return request.app.state.identity_context


security = HTTPBearer()


def get_user_claims(
    context: Annotated[Context, Depends(get_context)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> UserClaims:
    token = credentials.credentials
    return context.token_decoder.decode(token)
