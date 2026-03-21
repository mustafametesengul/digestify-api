import secrets
from uuid import UUID

import jwt
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from digestify_api.identity.token_generator import TokenPurpose, UserClaims, UserRole


class TokenDecoderSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_prefix="DIGESTIFY_API_",
    )

    secret_key: SecretStr = Field(
        default_factory=lambda: SecretStr(secrets.token_urlsafe(32))
    )
    algorithm: str = "HS256"


class TokenDecoder:
    def __init__(self, settings: TokenDecoderSettings | None = None) -> None:
        self._settings = settings or TokenDecoderSettings()

    def decode(
        self,
        token: str,
        purpose: TokenPurpose = TokenPurpose.ACCESS,
    ) -> UserClaims:
        payload = jwt.decode(
            token,
            self._settings.secret_key.get_secret_value(),
            algorithms=[self._settings.algorithm],
        )
        payload_token_type = payload.get("type")
        payload_sub = payload.get("sub")
        payload_role = payload.get("role")
        if (
            not isinstance(payload_sub, str)
            or not isinstance(payload_role, str)
            or not isinstance(payload_token_type, str)
        ):
            raise TypeError("Invalid token payload")

        token_purpose = TokenPurpose(payload_token_type)
        if token_purpose is not purpose:
            raise jwt.InvalidTokenError("Invalid token type")

        return UserClaims(
            id=UUID(payload_sub),
            role=UserRole(payload_role),
        )
