from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest
from pydantic import SecretStr

from digestify_api.identity.token import (
    TOKEN_AUDIENCE,
    TOKEN_ISSUER,
    TokenGenerator,
    TokenGeneratorSettings,
    TokenPurpose,
    TokenVerifier,
    TokenVerifierSettings,
    UserClaims,
    UserRole,
)
from tests.identity.test_service import SECRET


@pytest.mark.parametrize(
    "missing", ["exp", "iat", "sub", "role", "type", "jti", "iss", "aud", "gen"]
)
def test_verifier_requires_claims(missing: str) -> None:
    payload = {
        "sub": str(uuid4()),
        "role": "permanent",
        "type": "access",
        "exp": datetime.now(UTC) + timedelta(minutes=1),
        "iat": datetime.now(UTC),
        "iss": TOKEN_ISSUER,
        "aud": TOKEN_AUDIENCE,
        "jti": str(uuid4()),
        "gen": str(uuid4()),
    }
    del payload[missing]
    verifier = TokenVerifier(TokenVerifierSettings(secret_key=SecretStr(SECRET)))
    token = jwt.encode(payload, SECRET, algorithm="HS256")

    with pytest.raises(jwt.MissingRequiredClaimError):
        verifier.verify(token, TokenPurpose.ACCESS)


def test_verifier_rejects_expired_token() -> None:
    token = jwt.encode(
        {
            "sub": str(uuid4()),
            "role": "permanent",
            "type": "access",
            "exp": datetime.now(UTC) - timedelta(seconds=1),
            "iat": datetime.now(UTC) - timedelta(minutes=5),
            "iss": TOKEN_ISSUER,
            "aud": TOKEN_AUDIENCE,
            "jti": str(uuid4()),
        },
        SECRET,
        algorithm="HS256",
    )
    verifier = TokenVerifier(TokenVerifierSettings(secret_key=SecretStr(SECRET)))

    with pytest.raises(jwt.ExpiredSignatureError):
        verifier.verify(token, TokenPurpose.ACCESS)


def test_stateless_token_lifetimes_and_purposes() -> None:
    generator = TokenGenerator(TokenGeneratorSettings(secret_key=SecretStr(SECRET)))
    verifier = TokenVerifier(TokenVerifierSettings(secret_key=SecretStr(SECRET)))
    claims = UserClaims(id=uuid4(), role=UserRole.PERMANENT, token_generation=uuid4())
    pair = generator.generate(claims)
    for token, purpose, lifetime in (
        (pair.access_token, TokenPurpose.ACCESS, timedelta(minutes=5)),
        (pair.refresh_token, TokenPurpose.REFRESH, timedelta(days=45)),
    ):
        payload = jwt.decode(
            token, SECRET, algorithms=["HS256"], audience=TOKEN_AUDIENCE
        )
        assert payload["exp"] - payload["iat"] == lifetime.total_seconds()
        assert "sid" not in payload
        assert verifier.verify(token, purpose).id == claims.id
        assert (
            verifier.verify(token, purpose).token_generation == claims.token_generation
        )
    with pytest.raises(jwt.InvalidTokenError):
        verifier.verify(pair.access_token, TokenPurpose.REFRESH)


@pytest.mark.parametrize("claim", ["iss", "aud"])
def test_token_from_another_application_is_rejected(claim: str) -> None:
    generator = TokenGenerator(TokenGeneratorSettings(secret_key=SecretStr(SECRET)))
    pair = generator.generate(
        UserClaims(id=uuid4(), role=UserRole.PERMANENT, token_generation=uuid4())
    )

    payload = jwt.decode(
        pair.refresh_token, SECRET, algorithms=["HS256"], audience=TOKEN_AUDIENCE
    )
    payload[claim] = "another-application"
    token = jwt.encode(
        payload,
        SECRET,
        algorithm="HS256",
    )
    verifier = TokenVerifier(TokenVerifierSettings(secret_key=SecretStr(SECRET)))
    with pytest.raises(jwt.InvalidTokenError):
        verifier.verify(token, TokenPurpose.REFRESH)


@pytest.mark.parametrize("generation", [None, "not-a-uuid", 42, {}])
def test_registered_token_rejects_invalid_generation(generation: object) -> None:
    generator = TokenGenerator(TokenGeneratorSettings(secret_key=SecretStr(SECRET)))
    pair = generator.generate(
        UserClaims(id=uuid4(), role=UserRole.PERMANENT, token_generation=uuid4())
    )
    payload = jwt.decode(
        pair.access_token, SECRET, algorithms=["HS256"], audience=TOKEN_AUDIENCE
    )
    payload["gen"] = generation
    token = jwt.encode(payload, SECRET, algorithm="HS256")
    verifier = TokenVerifier(TokenVerifierSettings(secret_key=SecretStr(SECRET)))
    with pytest.raises(jwt.InvalidTokenError):
        verifier.verify(token, TokenPurpose.ACCESS)
