from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Literal
from uuid import UUID, uuid4

import jwt
from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

TOKEN_ISSUER = "digestify-api"
TOKEN_AUDIENCE = "digestify-api"


class TokenPurpose(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"


class UserRole(StrEnum):
    ANONYMOUS = "anonymous"
    PERMANENT = "permanent"
    ADMIN = "admin"


class UserClaims(BaseModel):
    id: UUID
    role: UserRole
    token_generation: UUID | None = None


class TokenClaims(UserClaims):
    token_id: UUID


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["Bearer"] = "Bearer"


class TokenVerifierSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_prefix="DIGESTIFY_API_",
    )

    secret_key: SecretStr = Field(default=...)
    algorithm: str = "HS256"


class TokenVerifier:
    def __init__(self, settings: TokenVerifierSettings | None = None) -> None:
        self._settings = settings or TokenVerifierSettings()

    def verify(self, token: str, purpose: TokenPurpose) -> TokenClaims:
        payload = jwt.decode(
            token,
            self._settings.secret_key.get_secret_value(),
            algorithms=[self._settings.algorithm],
            issuer=TOKEN_ISSUER,
            audience=TOKEN_AUDIENCE,
            options={
                "require": ["exp", "iat", "sub", "role", "type", "jti", "iss", "aud"]
            },
        )
        payload_token_type = payload.get("type")
        payload_sub = payload.get("sub")
        payload_role = payload.get("role")
        if (
            not isinstance(payload_sub, str)
            or not isinstance(payload_role, str)
            or not isinstance(payload_token_type, str)
        ):
            raise jwt.InvalidTokenError()

        try:
            token_purpose = TokenPurpose(payload_token_type)
            user_id = UUID(payload_sub)
            user_role = UserRole(payload_role)
            token_id = UUID(payload["jti"])
        except ValueError, TypeError, AttributeError:
            raise jwt.InvalidTokenError()

        if token_purpose is not purpose:
            raise jwt.InvalidTokenError()

        generation = None
        if user_role is not UserRole.ANONYMOUS:
            if "gen" not in payload:
                raise jwt.MissingRequiredClaimError("gen")
            try:
                generation = UUID(payload["gen"])
            except ValueError, TypeError, AttributeError:
                raise jwt.InvalidTokenError()
        return TokenClaims(
            id=user_id, role=user_role, token_id=token_id, token_generation=generation
        )


class TokenGeneratorSettings(TokenVerifierSettings):
    access_token_expire_minutes: int = Field(default=5, gt=0)
    refresh_token_expire_days: int = Field(default=45, gt=0)


class TokenGenerator:
    def __init__(self, settings: TokenGeneratorSettings | None = None) -> None:
        self._settings = settings or TokenGeneratorSettings()

    @property
    def refresh_token_lifetime(self) -> timedelta:
        return timedelta(days=self._settings.refresh_token_expire_days)

    def generate(self, user_claims: UserClaims) -> TokenPair:
        """Issue reusable bearer tokens; each refresh starts a new expiry window."""
        now = datetime.now(UTC)
        access_token_expire = now + timedelta(
            minutes=self._settings.access_token_expire_minutes
        )
        common = {
            "sub": str(user_claims.id),
            "role": user_claims.role.value,
            "iat": now,
            "iss": TOKEN_ISSUER,
            "aud": TOKEN_AUDIENCE,
        }
        if user_claims.role is not UserRole.ANONYMOUS:
            if user_claims.token_generation is None:
                raise ValueError(
                    "Registered-user tokens require an account generation."
                )
            common["gen"] = str(user_claims.token_generation)
        to_encode = {
            **common,
            "exp": access_token_expire,
            "type": TokenPurpose.ACCESS.value,
            "jti": str(uuid4()),
        }
        access_token = jwt.encode(
            to_encode,
            self._settings.secret_key.get_secret_value(),
            algorithm=self._settings.algorithm,
        )

        to_encode = {
            **common,
            "exp": now + self.refresh_token_lifetime,
            "type": TokenPurpose.REFRESH.value,
            "jti": str(uuid4()),
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
