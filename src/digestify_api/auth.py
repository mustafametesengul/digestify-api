import base64
import logging
from typing import Annotated
from uuid import UUID

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from pydantic import BaseModel

from digestify_api.settings import get_settings

logger = logging.getLogger(__name__)


class Auth(BaseModel):
    id: UUID
    is_anonymous: bool


_public_keys = {}
_security = HTTPBearer()


def b64url_decode(val: str) -> bytes:
    rem = len(val) % 4
    if rem:
        val += "=" * (4 - rem)
    return base64.urlsafe_b64decode(val)


def jwk_to_public_key(jwk):
    x_bytes = b64url_decode(jwk["x"])
    y_bytes = b64url_decode(jwk["y"])
    public_numbers = ec.EllipticCurvePublicNumbers(
        int.from_bytes(x_bytes, "big"),
        int.from_bytes(y_bytes, "big"),
        ec.SECP256R1(),  # P-256
    )
    return public_numbers.public_key()


async def fetch_jwks():
    """Fetch JWKS from Supabase on startup."""
    global _public_keys
    settings = get_settings()
    async with httpx.AsyncClient() as client:
        resp = await client.get(settings.jwks_url)
        resp.raise_for_status()
        jwks = resp.json()
        for jwk in jwks["keys"]:
            kid = jwk["kid"]
            _public_keys[kid] = jwk_to_public_key(jwk)
    logger.info(f"Loaded {len(_public_keys)} public keys from Supabase.")


def verify_jwt_token(token: str) -> dict:
    """Verify JWT using the correct public key from kid."""
    try:
        unverified_header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token header: {str(e)}")

    kid = unverified_header.get("kid")
    if kid not in _public_keys:
        raise HTTPException(status_code=401, detail="Unknown key ID")

    public_key = _public_keys[kid]

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
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_security)],
) -> Auth:
    token = credentials.credentials
    decoded_token = verify_jwt_token(token)
    user_id = UUID(decoded_token["sub"])
    is_anonymous = bool(decoded_token.get("is_anonymous", False))
    auth = Auth(id=user_id, is_anonymous=is_anonymous)
    return auth


def mock_get_auth() -> Auth:
    return Auth(id=UUID("12345678-1234-5678-1234-567812345678"), is_anonymous=False)
