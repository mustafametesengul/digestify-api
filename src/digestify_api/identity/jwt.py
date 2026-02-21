import secrets
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import ExpiredSignatureError, InvalidTokenError
from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class InvalidCredentials(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials provided",
            headers={"WWW-Authenticate": "Bearer"},
        )


class TokenExpired(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )


class NonAnonymousAccessRequired(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Non-anonymous access required for this resource",
        )


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"


class TokenPayload(BaseModel):
    id: UUID
    is_anonymous: bool


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["Bearer"] = "Bearer"


class JWTSettings(BaseSettings):
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


class JWTService:
    def __init__(self, settings: JWTSettings | None = None) -> None:
        self._settings = settings or JWTSettings()

    def generate_tokens(self, payload: TokenPayload) -> TokenResponse:
        access_token_expire = datetime.now(timezone.utc) + timedelta(
            minutes=self._settings.access_token_expire_minutes
        )
        to_encode = {
            "sub": str(payload.id),
            "exp": access_token_expire,
            "anon": payload.is_anonymous,
            "type": TokenType.ACCESS.value,
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
            "sub": str(payload.id),
            "exp": refresh_token_expire,
            "anon": payload.is_anonymous,
            "type": TokenType.REFRESH.value,
        }
        refresh_token = jwt.encode(
            to_encode,
            self._settings.secret_key.get_secret_value(),
            algorithm=self._settings.algorithm,
        )

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
        )

    def decode_token(
        self,
        token: str,
        token_type: TokenType = TokenType.ACCESS,
    ) -> TokenPayload:
        """Verify JWT using the secret key."""
        try:
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
                or payload_token_type != token_type.value
            ):
                raise InvalidCredentials()

            return TokenPayload(
                id=UUID(payload_sub),
                is_anonymous=payload_anon,
            )
        except ExpiredSignatureError:
            raise TokenExpired()
        except InvalidTokenError:
            raise InvalidCredentials()


jwt_service = JWTService()
security = HTTPBearer()


def get_jwt_service() -> JWTService:
    return jwt_service


def get_token_payload(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
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
