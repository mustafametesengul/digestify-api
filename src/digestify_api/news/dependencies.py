from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from digestify_api.infrastructure.database import Database
from digestify_api.infrastructure.token_generation import TokenPurpose, UserClaims
from digestify_api.infrastructure.token_verification import TokenVerifier
from digestify_api.news.models import Checkpoint, Story, Topic, User


class Unauthenticated(HTTPException):
    def __init__(self, detail: str = "Could not validate credentials") -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


@dataclass
class Context:
    database: Database[User | Topic | Story | Checkpoint]
    token_verifier: TokenVerifier


def get_context(request: Request) -> Context:
    return request.app.state.news_context


http_bearer = HTTPBearer()


def require_authenticated_user(
    context: Annotated[Context, Depends(get_context)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(http_bearer)],
) -> UserClaims:
    token = credentials.credentials
    try:
        return context.token_verifier.verify(token, purpose=TokenPurpose.ACCESS)
    except jwt.PyJWTError:
        raise Unauthenticated()
