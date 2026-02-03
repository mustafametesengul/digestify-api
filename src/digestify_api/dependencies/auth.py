import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any
from uuid import UUID

import bcrypt
import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
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

    secret_key: SecretStr = Field(default=SecretStr("default_secret_key"))
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

    def create_access_token(self, data: dict) -> str:
        to_encode = data.copy()

        expire = datetime.now(timezone.utc) + timedelta(
            minutes=self._settings.access_token_expire_minutes
        )
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(
            to_encode,
            self._settings.secret_key.get_secret_value(),
            algorithm=self._settings.algorithm,
        )
        return encoded_jwt

    def create_refresh_token(self, data: dict) -> str:
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + timedelta(
            days=self._settings.refresh_token_expire_days
        )
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(
            to_encode,
            self._settings.secret_key.get_secret_value(),
            algorithm=self._settings.algorithm,
        )
        return encoded_jwt

    def verify_jwt_token(self, token: str) -> dict[str, Any]:
        """Verify JWT using the secret key."""
        try:
            payload = jwt.decode(
                token,
                self._settings.secret_key.get_secret_value(),
                algorithms=[self._settings.algorithm],
            )
            return payload
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
    decoded_token = auth_manager.verify_jwt_token(token)
    user_id = UUID(decoded_token["sub"])
    auth = models.auth.Auth(id=user_id)
    return auth
