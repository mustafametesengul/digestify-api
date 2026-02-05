import asyncio
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

import bcrypt
import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import ExpiredSignatureError, InvalidTokenError
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from digestify_api import exceptions, models

_logger = logging.getLogger(__name__)


class AuthSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_prefix="DIGESTIFY_API_",
    )

    secret_key: SecretStr = Field(
        default_factory=lambda: SecretStr(secrets.token_urlsafe(32))
    )
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7


class AuthManager:
    def __init__(self, settings: AuthSettings) -> None:
        self._settings = settings

    async def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return await asyncio.to_thread(
            bcrypt.checkpw,
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )

    async def hash_password(self, password: str) -> str:
        hashed_bytes = await asyncio.to_thread(
            bcrypt.hashpw,
            password.encode("utf-8"),
            bcrypt.gensalt(),
        )
        return hashed_bytes.decode("utf-8")

    def create_tokens(self, auth: models.auth.Auth) -> models.auth.TokenResponse:
        access_token_expire = datetime.now(timezone.utc) + timedelta(
            minutes=self._settings.access_token_expire_minutes
        )
        to_encode = {
            "sub": str(auth.id),
            "exp": access_token_expire,
            "anon": auth.is_anonymous,
            "type": "access",
        }
        access_token = jwt.encode(
            to_encode,
            self._settings.secret_key.get_secret_value(),
            algorithm=self._settings.algorithm,
        )

        refresh_token_expire = datetime.now(timezone.utc) + timedelta(
            days=self._settings.refresh_token_expire_days
        )
        to_encode = {
            "sub": str(auth.id),
            "exp": refresh_token_expire,
            "anon": auth.is_anonymous,
            "type": "refresh",
        }
        refresh_token = jwt.encode(
            to_encode,
            self._settings.secret_key.get_secret_value(),
            algorithm=self._settings.algorithm,
        )

        return models.auth.TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="Bearer",
        )

    def verify_jwt_token(
        self, token: str, token_type: str = "access"
    ) -> models.auth.Auth:
        """Verify JWT using the secret key."""
        try:
            payload = jwt.decode(
                token,
                self._settings.secret_key.get_secret_value(),
                algorithms=[self._settings.algorithm],
            )
            if payload.get("type") != token_type:
                raise exceptions.auth.InvalidCredentials()

            return models.auth.Auth(
                id=UUID(payload["sub"]),
                is_anonymous=bool(payload["anon"]),
            )
        except ExpiredSignatureError:
            raise exceptions.auth.TokenExpired()
        except InvalidTokenError:
            raise exceptions.auth.InvalidCredentials()


_auth_manager: AuthManager | None = None
_security = HTTPBearer()


def init_auth_manager(settings: AuthSettings) -> AuthManager:
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
) -> models.auth.Auth:
    auth_manager = get_auth_manager()
    token = credentials.credentials
    return auth_manager.verify_jwt_token(token, token_type="access")


def get_non_anonymous_auth(
    auth: Annotated[models.auth.Auth, Depends(get_auth)],
) -> models.auth.Auth:
    if auth.is_anonymous:
        raise exceptions.auth.InvalidCredentials()
    return auth
