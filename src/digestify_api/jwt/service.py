from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from jwt import ExpiredSignatureError, InvalidTokenError

from digestify_api.jwt.exceptions import InvalidCredentials, TokenExpired
from digestify_api.jwt.models import TokenPayload, TokenResponse, TokenType
from digestify_api.jwt.settings import JWTSettings


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
