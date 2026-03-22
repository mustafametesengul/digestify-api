from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Literal
from uuid import UUID, uuid4

import jwt
from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class TokenPurpose(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"


class UserRole(StrEnum):
    ANONYMOUS = "anonymous"
    PERMANENT = "permanent"
    ADMIN = "admin"


class UserClaims(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    role: UserRole


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["Bearer"] = "Bearer"


class TokenGeneratorSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_prefix="DIGESTIFY_API_",
    )

    secret_key: SecretStr = Field(default=...)
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7


class TokenGenerator:
    def __init__(self, settings: TokenGeneratorSettings | None = None) -> None:
        self._settings = settings or TokenGeneratorSettings()

    def generate(self, user_claims: UserClaims) -> TokenPair:
        access_token_expire = datetime.now(timezone.utc) + timedelta(
            minutes=self._settings.access_token_expire_minutes
        )
        to_encode = {
            "sub": str(user_claims.id),
            "exp": access_token_expire,
            "role": user_claims.role.value,
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
            "role": user_claims.role.value,
            "type": TokenPurpose.REFRESH.value,
        }
        refresh_token = jwt.encode(
            to_encode,
            self._settings.secret_key.get_secret_value(),
            algorithm=self._settings.algorithm,
        )

        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
        )
