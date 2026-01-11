import base64
import logging
from typing import Annotated, Any
from uuid import UUID

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


public_keys: dict[str, ec.EllipticCurvePublicKey] = {}
security = HTTPBearer()


class AuthSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    jwks_url: str = Field(default=...)


class Auth(BaseModel):
    id: UUID
    is_anonymous: bool


def b64url_decode(val: str) -> bytes:
    rem = len(val) % 4
    if rem:
        val += "=" * (4 - rem)
    return base64.urlsafe_b64decode(val)


def jwk_to_public_key(jwk: dict[str, str]) -> ec.EllipticCurvePublicKey:
    x_bytes = b64url_decode(jwk["x"])
    y_bytes = b64url_decode(jwk["y"])
    public_numbers = ec.EllipticCurvePublicNumbers(
        int.from_bytes(x_bytes, "big"),
        int.from_bytes(y_bytes, "big"),
        ec.SECP256R1(),
    )
    return public_numbers.public_key()


async def fetch_jwks(settings: AuthSettings | None = None) -> None:
    """Fetch JWKS on startup."""
    global public_keys
    if settings is None:
        settings = AuthSettings()
    async with httpx.AsyncClient() as client:
        resp = await client.get(settings.jwks_url)
        resp.raise_for_status()
        jwks = resp.json()
        for jwk in jwks["keys"]:
            kid = jwk["kid"]
            public_keys[kid] = jwk_to_public_key(jwk)
    logger.info(f"Loaded {len(public_keys)} public keys.")


def verify_jwt_token(token: str) -> dict[str, Any]:
    """Verify JWT using the correct public key from kid."""
    try:
        unverified_header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token header: {str(e)}")

    kid = unverified_header["kid"]
    if not isinstance(kid, str):
        raise HTTPException(status_code=401, detail="Invalid key ID in token header")
    if kid not in public_keys:
        raise HTTPException(status_code=401, detail="Unknown key ID")

    public_key = public_keys[kid]

    try:
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["ES256"],
            audience="authenticated",
        )
        return payload
    except InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")


def get_auth(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> Auth:
    token = credentials.credentials
    decoded_token = verify_jwt_token(token)
    user_id = UUID(decoded_token["sub"])
    is_anonymous = bool(decoded_token.get("is_anonymous", False))
    auth = Auth(id=user_id, is_anonymous=is_anonymous)
    return auth


def mock_get_auth() -> Auth:
    return Auth(id=UUID("12345678-1234-5678-1234-567812345678"), is_anonymous=False)
