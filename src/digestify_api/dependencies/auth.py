from typing import Annotated
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from digestify_api.core import AuthManager, AuthSettings
from digestify_api.models.auth import Auth

_auth_manager: AuthManager | None = None
_security = HTTPBearer()


def init_auth_manager(settings: AuthSettings | None = None) -> AuthManager:
    global _auth_manager
    _auth_manager = AuthManager(settings)
    return _auth_manager


def get_auth_manager() -> AuthManager:
    global _auth_manager
    if _auth_manager is None:
        raise RuntimeError("Auth service is not initialized.")
    return _auth_manager


def get_auth(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_security)],
) -> Auth:
    auth_manager = get_auth_manager()
    token = credentials.credentials
    decoded_token = auth_manager.verify_jwt_token(token)
    user_id = UUID(decoded_token["sub"])
    is_anonymous = bool(decoded_token.get("is_anonymous", False))
    auth = Auth(id=user_id, is_anonymous=is_anonymous)
    return auth


def mock_get_auth() -> Auth:
    return Auth(id=UUID("12345678-1234-5678-1234-567812345678"), is_anonymous=False)
