import base64
import logging
from typing import Any

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import ec
from jwt import InvalidTokenError
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from digestify_api.exceptions.auth import InvalidCredentials


class AuthSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_prefix="DIGESTIFY_API_",
    )

    jwks_url: str = Field(default=...)


_logger = logging.getLogger(__name__)


class AuthManager:
    def __init__(self, settings: AuthSettings | None = None) -> None:
        if settings is None:
            settings = AuthSettings()
        self.settings = settings

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
        if self.settings is None:
            self.settings = AuthSettings()
        async with httpx.AsyncClient() as client:
            resp = await client.get(self.settings.jwks_url)
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
