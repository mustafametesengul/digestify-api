import base64
import logging
from typing import Annotated, Any
from uuid import UUID

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from digestify_api.exceptions.auth import InvalidCredentials
from digestify_api.models import Auth

_logger = logging.getLogger(__name__)


class AuthSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_prefix="DIGESTIFY_API_",
    )

    jwks_url: str = Field(default=...)


class AuthManager:
    def __init__(self, settings: AuthSettings) -> None:
        self._settings = settings

        self._public_keys: dict[str, ec.EllipticCurvePublicKey] = {}

    def b64url_decode(self, val: str) -> bytes:
        rem = len(val) % 4
        if rem:
            val += "=" * (4 - rem)
        return base64.urlsafe_b64decode(val)

    def jwk_to_public_key(self, jwk: dict[str, str]) -> ec.EllipticCurvePublicKey:
        x_bytes = self.b64url_decode(jwk["x"])
        y_bytes = self.b64url_decode(jwk["y"])
        public_numbers = ec.EllipticCurvePublicNumbers(
            int.from_bytes(x_bytes, "big"),
            int.from_bytes(y_bytes, "big"),
            ec.SECP256R1(),
        )
        return public_numbers.public_key()

    async def fetch_jwks(self) -> None:
        """Fetch JWKS on startup."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(self._settings.jwks_url)
            resp.raise_for_status()
            jwks = resp.json()
            for jwk in jwks["keys"]:
                kid = jwk["kid"]
                self._public_keys[kid] = self.jwk_to_public_key(jwk)
        _logger.info(f"Loaded {len(self._public_keys)} public keys.")

    def verify_jwt_token(self, token: str) -> dict[str, Any]:
        """Verify JWT using the correct public key from kid."""
        try:
            unverified_header = jwt.get_unverified_header(token)
        except jwt.PyJWTError:
            raise InvalidCredentials()

        kid = unverified_header["kid"]
        if not isinstance(kid, str):
            raise InvalidCredentials()
        if kid not in self._public_keys:
            raise InvalidCredentials()

        public_key = self._public_keys[kid]

        try:
            payload = jwt.decode(
                token,
                public_key,
                algorithms=["ES256"],
                audience="authenticated",
            )
            return payload
        except InvalidTokenError:
            raise InvalidCredentials()


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
