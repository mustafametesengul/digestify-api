from typing import Annotated
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from digestify_api.auth.models import Auth
from digestify_api.auth.service import AuthService, AuthSettings

_auth_service: AuthService | None = None
_security = HTTPBearer()


def init_auth_service(settings: AuthSettings | None = None) -> AuthService:
    global _auth_service
    _auth_service = AuthService(settings)
    return _auth_service


def get_auth_service() -> AuthService:
    global _auth_service
    if _auth_service is None:
        raise RuntimeError("Auth service is not initialized.")
    return _auth_service


def get_auth(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_security)],
) -> Auth:
    auth_service = get_auth_service()
    token = credentials.credentials
    decoded_token = auth_service.verify_jwt_token(token)
    user_id = UUID(decoded_token["sub"])
    is_anonymous = bool(decoded_token.get("is_anonymous", False))
    auth = Auth(id=user_id, is_anonymous=is_anonymous)
    return auth


def mock_get_auth() -> Auth:
    return Auth(id=UUID("12345678-1234-5678-1234-567812345678"), is_anonymous=False)
