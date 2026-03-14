import secrets
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Literal
from uuid import UUID

import jwt
from jwt import InvalidTokenError
from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class UserClaims(BaseModel):
    id: UUID
    is_anonymous: bool


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["Bearer"] = "Bearer"


class TokenPurpose(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"


class TokenManagerSettings(BaseSettings):
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


class TokenManager:
    def __init__(self, settings: TokenManagerSettings | None = None) -> None:
        self._settings = settings or TokenManagerSettings()

    def generate(self, user_claims: UserClaims) -> Token:
        access_token_expire = datetime.now(timezone.utc) + timedelta(
            minutes=self._settings.access_token_expire_minutes
        )
        to_encode = {
            "sub": str(user_claims.id),
            "exp": access_token_expire,
            "anon": user_claims.is_anonymous,
            "type": TokenPurpose.ACCESS.value,
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
            "sub": str(user_claims.id),
            "exp": refresh_token_expire,
            "anon": user_claims.is_anonymous,
            "type": TokenPurpose.REFRESH.value,
        }
        refresh_token = jwt.encode(
            to_encode,
            self._settings.secret_key.get_secret_value(),
            algorithm=self._settings.algorithm,
        )

        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
        )

    def decode(
        self,
        token: str,
        purpose: TokenPurpose = TokenPurpose.ACCESS,
    ) -> UserClaims:
        """Verify JWT using the secret key."""
        payload = jwt.decode(
            token,
            self._settings.secret_key.get_secret_value(),
            algorithms=[self._settings.algorithm],
        )
        payload_token_type = payload.get("type")
        payload_sub = payload.get("sub")
        payload_anon = payload.get("anon")
        if (
            not isinstance(payload_sub, str)
            or not isinstance(payload_anon, bool)
            or not isinstance(payload_token_type, str)
        ):
            raise TypeError("Invalid token payload")

        if payload_token_type != purpose.value:
            raise InvalidTokenError("Invalid token type")

        return UserClaims(
            id=UUID(payload_sub),
            is_anonymous=payload_anon,
        )
