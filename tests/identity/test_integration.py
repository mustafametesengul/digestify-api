import asyncio

import httpx
import jwt
import pytest
from pydantic import SecretStr

from digestify_api.couchdb import (
    Database,
    Document,
    Repository,
    UnresolvedDocumentConflict,
)
from digestify_api.identity import identity as identity_module
from digestify_api.identity.sign_in_code import InvalidCode, SignInCode
from digestify_api.identity.token import (
    TokenGenerator,
    TokenGeneratorSettings,
    TokenPurpose,
    TokenVerifier,
    TokenVerifierSettings,
)
from digestify_api.identity.user import User
from tests.couchdb.test_integration import client as client
from tests.couchdb.test_integration import database as database
from tests.couchdb.test_integration import pytestmark as pytestmark
from tests.identity.test_service import EMAIL, SECRET, Identity, RecordingEmailClient


@pytest.fixture
def identity(database: Database) -> Identity:
    users = Repository(User, database)
    codes = Repository(SignInCode, database)
    email = RecordingEmailClient()
    verifier = TokenVerifier(TokenVerifierSettings(secret_key=SecretStr(SECRET)))
    return Identity(
        service=identity_module.Identity(
            users=users,
            sign_in_codes=codes,
            email_sender=email,
            token_generator=TokenGenerator(
                TokenGeneratorSettings(secret_key=SecretStr(SECRET))
            ),
            token_verifier=verifier,
        ),
        users=users,
        sign_in_codes=codes,
        email=email,
        verifier=verifier,
    )


def synchronize_first_reads[Model: Document](
    repository: Repository[Model], monkeypatch: pytest.MonkeyPatch
) -> None:
    original_get = repository.get
    ready = asyncio.Event()
    reads = 0

    async def synchronized_get(id: str) -> Model | None:
        nonlocal reads
        document = await original_get(id)
        reads += 1
        if reads <= 2:
            if reads == 2:
                ready.set()
            await ready.wait()
        return document

    monkeypatch.setattr(repository, "get", synchronized_get)


async def test_concurrent_sign_in_creates_one_account(
    identity: Identity, monkeypatch: pytest.MonkeyPatch
) -> None:
    await identity.service.sign_in_with_email(EMAIL)
    synchronize_first_reads(identity.sign_in_codes, monkeypatch)
    async with asyncio.timeout(15):
        results = await asyncio.gather(
            identity.service.verify_sign_in_code(EMAIL, identity.email.last_code),
            identity.service.verify_sign_in_code(EMAIL, identity.email.last_code),
            return_exceptions=True,
        )
    assert sum(isinstance(result, InvalidCode) for result in results) == 1
    assert sum(not isinstance(result, BaseException) for result in results) == 1
    [user] = await identity.users.find()
    sign_in = await identity.sign_in_codes.get(SignInCode.id_for(EMAIL))
    assert sign_in is not None
    assert str(sign_in.user_id) == user.id
    assert sign_in.challenge is None


async def test_concurrent_refresh_requires_no_writes(identity: Identity) -> None:
    await identity.service.sign_in_with_email(EMAIL)
    pair = await identity.service.verify_sign_in_code(EMAIL, identity.email.last_code)
    before = await identity.users.find()
    async with asyncio.timeout(15):
        results = await asyncio.gather(
            identity.service.refresh_token_pair(pair.refresh_token),
            identity.service.refresh_token_pair(pair.refresh_token),
        )
    assert await identity.users.find() == before
    for result in results:
        claims = identity.verifier.verify(result.access_token, TokenPurpose.ACCESS)
        await identity.service.authorize(claims)


async def test_recovery_persists_generation_and_rejects_old_tokens(
    identity: Identity,
) -> None:
    await identity.service.sign_in_with_email(EMAIL)
    old_pair = await identity.service.verify_sign_in_code(
        EMAIL, identity.email.last_code
    )
    old_claims = identity.verifier.verify(old_pair.access_token, TokenPurpose.ACCESS)
    await identity.reset_cooldown()
    await identity.service.sign_in_with_email(EMAIL)
    new_pair = await identity.service.verify_sign_in_code(
        EMAIL, identity.email.last_code, revoke_tokens=True
    )
    new_claims = identity.verifier.verify(new_pair.access_token, TokenPurpose.ACCESS)
    user = await identity.users.get(str(old_claims.id))
    assert user is not None
    assert user.token_generation == new_claims.token_generation
    assert user.token_generation != old_claims.token_generation
    assert new_claims.id == old_claims.id
    with pytest.raises(jwt.InvalidTokenError):
        await identity.service.authorize(old_claims)
    with pytest.raises(jwt.InvalidTokenError):
        await identity.service.refresh_token_pair(old_pair.refresh_token)
    await identity.service.authorize(new_claims)
    await identity.service.refresh_token_pair(new_pair.refresh_token)


@pytest.mark.parametrize("kind", ["user", "sign_in_code", "token_generation"])
async def test_replicated_conflicts_block_identity(
    identity: Identity, database: Database, client: httpx.AsyncClient, kind: str
) -> None:
    await identity.service.sign_in_with_email(EMAIL)
    pair = await identity.service.verify_sign_in_code(EMAIL, identity.email.last_code)
    claims = identity.verifier.verify(pair.access_token, TokenPurpose.ACCESS)
    id = str(claims.id) if kind != "sign_in_code" else SignInCode.id_for(EMAIL)
    original = await database.get(id)
    assert original is not None
    await database.save(id, {**original, "test_branch": "first"})
    generation, parent_hash = original["_rev"].split("-", 1)
    next_generation = int(generation) + 1
    conflicting = {
        **original,
        "_rev": f"{next_generation}-{'f' * 32}",
        "_revisions": {"start": next_generation, "ids": ["f" * 32, parent_hash]},
        "test_branch": "second",
    }
    if kind == "user":
        conflicting["is_deleted"] = True
    elif kind == "token_generation":
        user = await identity.users.get(str(claims.id))
        assert user is not None
        user.revoke_tokens()
        conflicting["token_generation"] = str(user.token_generation)
    response = await client.post(
        f"/{database.name}/_bulk_docs",
        json={"new_edits": False, "docs": [conflicting]},
    )
    response.raise_for_status()
    raw = await database.get(id, conflicts=True)
    assert raw is not None and raw.get("_conflicts")
    if kind != "sign_in_code":
        with pytest.raises(UnresolvedDocumentConflict):
            await identity.service.refresh_token_pair(pair.refresh_token)
        with pytest.raises(UnresolvedDocumentConflict):
            await identity.service.authorize(claims)
    else:
        with pytest.raises(UnresolvedDocumentConflict):
            await identity.service.sign_in_with_email(EMAIL)
        with pytest.raises(UnresolvedDocumentConflict):
            await identity.service.verify_sign_in_code(EMAIL, identity.email.last_code)
