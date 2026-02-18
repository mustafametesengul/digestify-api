from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from digestify_api.jwt.exceptions import InvalidCredentials
from digestify_api.jwt.models import TokenPayload, TokenType
from digestify_api.jwt.service import JWTService

_jwt_service = JWTService()
_security = HTTPBearer()


def get_jwt_service() -> JWTService:
    return _jwt_service


def get_token_payload(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_security)],
) -> TokenPayload:
    jwt_service = get_jwt_service()
    token = credentials.credentials
    return jwt_service.decode_token(token, token_type=TokenType.ACCESS)


def get_non_anonymous_token_payload(
    token_payload: Annotated[TokenPayload, Depends(get_token_payload)],
) -> TokenPayload:
    if token_payload.is_anonymous:
        raise InvalidCredentials()
    return token_payload
