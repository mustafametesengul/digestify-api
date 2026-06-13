from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from digestify_api.infrastructure.couchdb import DocumentRepository
from digestify_api.infrastructure.token_generation import TokenPurpose, UserClaims
from digestify_api.infrastructure.token_verification import TokenVerifier
from digestify_api.news.quota import FetchQuota
from digestify_api.news.story import Story
from digestify_api.news.topic import Topic
from digestify_api.news.user import User


class Unauthenticated(HTTPException):
    def __init__(self, detail: str = "Could not validate credentials") -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


@dataclass
class Context:
    users: DocumentRepository[User]
    topics: DocumentRepository[Topic]
    stories: DocumentRepository[Story]
    quotas: DocumentRepository[FetchQuota]
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
