import asyncio
import json
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import jwt
import pytest
from pydantic import SecretStr

from digestify_api.couchdb import Database, Repository, UnresolvedDocumentConflict
from digestify_api.identity.email import EmailClient
from digestify_api.identity.service import Service
from digestify_api.identity.sign_in_code import (
    CodeRequestedTooSoon,
    InvalidCode,
    SignInCode,
)
from digestify_api.identity.token import (
    TOKEN_AUDIENCE,
    TokenGenerator,
    TokenGeneratorSettings,
    TokenPurpose,
    TokenVerifier,
    TokenVerifierSettings,
    UserClaims,
    UserRole,
)
from digestify_api.identity.user import User

SECRET = "unit-test-secret-key-0123456789abcdef"

EMAIL = "alice@example.com"


class InMemoryCouch:
    """Just enough of CouchDB's document API for the service: GET and PUT."""

    def __init__(self) -> None:
        self.docs: dict[str, dict[str, Any]] = {}
        self._revision = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        _, doc_id = request.url.path.strip("/").split("/")
        if request.method == "GET":
            doc = self.docs.get(doc_id)
            if doc is None:
                return httpx.Response(404, json={"error": "not_found"})
            return httpx.Response(200, json=doc)
        if request.method == "PUT":
            doc = json.loads(request.content)
            existing = self.docs.get(doc_id)
            current_rev = existing["_rev"] if existing else None
            if doc.get("_rev") != current_rev:
                return httpx.Response(409, json={"error": "conflict"})
            self._revision += 1
            rev = f"{self._revision}-abc"
            self.docs[doc_id] = {**doc, "_id": doc_id, "_rev": rev}
            return httpx.Response(201, json={"ok": True, "id": doc_id, "rev": rev})
        raise AssertionError(f"unexpected request: {request.method} {request.url}")


class RecordingEmailClient(EmailClient):
    def __init__(self) -> None:
        self.sent: list[dict[str, str]] = []

    async def send(self, to: str, subject: str, text: str) -> None:
        self.sent.append({"to": to, "subject": subject, "text": text})

    @property
    def last_code(self) -> str:
        match = re.search(r"\b(\d{6})\b", self.sent[-1]["text"])
        assert match is not None, f"no code in {self.sent[-1]['text']!r}"
        return match.group(1)


@dataclass
class Identity:
    service: Service
    users: Repository[User]
    sign_in_codes: Repository[SignInCode]
    email: RecordingEmailClient
    verifier: TokenVerifier
    couch: InMemoryCouch | None = None

    async def sign_in(self, email: str = EMAIL) -> UserClaims:
        """Complete a full email sign-in and return the access-token claims."""
        await self.reset_cooldown(email)
        await self.service.sign_in_with_email(email)
        pair = await self.service.verify_sign_in_code(email, self.email.last_code)
        return self.verifier.verify(pair.access_token, purpose=TokenPurpose.ACCESS)

    async def reset_cooldown(self, email: str = EMAIL) -> None:
        sign_in = await self.sign_in_codes.get(SignInCode.id_for(email))
        if sign_in is not None:
            sign_in.last_issued_at = None
            await self.sign_in_codes.save(sign_in)


@pytest.fixture
async def identity() -> AsyncIterator[Identity]:
    couch = InMemoryCouch()
    async with httpx.AsyncClient(
        base_url="http://couch",
        transport=httpx.MockTransport(couch),
    ) as client:
        database = Database(client, "identity")
        users = Repository(User, database)
        sign_in_codes = Repository(SignInCode, database)
        email = RecordingEmailClient()
        verifier = TokenVerifier(
            TokenVerifierSettings(secret_key=SecretStr(SECRET)),
        )
        yield Identity(
            service=Service(
                users=users,
                sign_in_codes=sign_in_codes,
                email_sender=email,
                token_generator=TokenGenerator(
                    TokenGeneratorSettings(secret_key=SecretStr(SECRET)),
                ),
                token_verifier=verifier,
            ),
            users=users,
            sign_in_codes=sign_in_codes,
            email=email,
            verifier=verifier,
            couch=couch,
        )


async def test_sign_in_anonymously_issues_anonymous_tokens(
    identity: Identity,
) -> None:
    pair = await identity.service.sign_in_anonymously()

    claims = identity.verifier.verify(pair.access_token, purpose=TokenPurpose.ACCESS)
    assert claims.role is UserRole.ANONYMOUS


async def test_sign_in_with_email_sends_code_to_normalized_address(
    identity: Identity,
) -> None:
    await identity.service.sign_in_with_email("  Alice@Example.COM ")

    assert [sent["to"] for sent in identity.email.sent] == [EMAIL]
    assert identity.email.last_code.isdigit()


async def test_sign_in_with_email_enforces_cooldown(identity: Identity) -> None:
    await identity.service.sign_in_with_email(EMAIL)

    with pytest.raises(CodeRequestedTooSoon):
        await identity.service.sign_in_with_email(EMAIL)


async def test_verify_sign_in_code_creates_permanent_user(
    identity: Identity,
) -> None:
    claims = await identity.sign_in()

    assert claims.role is UserRole.PERMANENT
    assert await identity.service.get_email(claims) == EMAIL

    user = await identity.users.get(str(claims.id))
    assert user is not None
    assert user.email == EMAIL


async def test_verify_sign_in_code_rejects_unknown_email(identity: Identity) -> None:
    with pytest.raises(InvalidCode):
        await identity.service.verify_sign_in_code(EMAIL, "123456")


async def test_verify_sign_in_code_persists_consumed_attempts(
    identity: Identity,
) -> None:
    await identity.service.sign_in_with_email(EMAIL)
    code = identity.email.last_code
    wrong = "000000" if code != "000000" else "999999"

    with pytest.raises(InvalidCode):
        await identity.service.verify_sign_in_code(EMAIL, wrong)

    sign_in = await identity.sign_in_codes.get(SignInCode.id_for(EMAIL))
    assert sign_in is not None
    assert sign_in.challenge is not None
    assert sign_in.challenge.attempts_remaining == 4

    # The right code still signs in after a failed guess.
    pair = await identity.service.verify_sign_in_code(EMAIL, code)
    claims = identity.verifier.verify(pair.access_token, purpose=TokenPurpose.ACCESS)
    assert claims.role is UserRole.PERMANENT


async def test_returning_user_keeps_their_id(identity: Identity) -> None:
    first = await identity.sign_in()
    second = await identity.sign_in()

    assert second.id == first.id


async def test_refresh_token_pair_renews_tokens(identity: Identity) -> None:
    await identity.reset_cooldown()
    await identity.service.sign_in_with_email(EMAIL)
    pair = await identity.service.verify_sign_in_code(EMAIL, identity.email.last_code)

    refreshed = await identity.service.refresh_token_pair(pair.refresh_token)

    claims = identity.verifier.verify(
        refreshed.access_token, purpose=TokenPurpose.ACCESS
    )
    assert claims.role is UserRole.PERMANENT


async def test_refresh_rejects_access_token(identity: Identity) -> None:
    pair = await identity.service.sign_in_anonymously()

    with pytest.raises(jwt.InvalidTokenError):
        await identity.service.refresh_token_pair(pair.access_token)


async def test_delete_account_revokes_access(identity: Identity) -> None:
    claims = await identity.sign_in()

    await identity.service.delete_account(claims)

    with pytest.raises(jwt.InvalidTokenError):
        await identity.service.get_email(claims)
    with pytest.raises(jwt.InvalidTokenError):
        await identity.service.delete_account(claims)


async def test_deleted_user_cannot_refresh(identity: Identity) -> None:
    await identity.reset_cooldown()
    await identity.service.sign_in_with_email(EMAIL)
    pair = await identity.service.verify_sign_in_code(EMAIL, identity.email.last_code)
    claims = identity.verifier.verify(pair.access_token, purpose=TokenPurpose.ACCESS)

    await identity.service.delete_account(claims)

    with pytest.raises(jwt.InvalidTokenError):
        await identity.service.refresh_token_pair(pair.refresh_token)


async def test_sign_in_after_deletion_creates_fresh_user(
    identity: Identity,
) -> None:
    first = await identity.sign_in()
    await identity.service.delete_account(first)

    second = await identity.sign_in()

    assert second.id != first.id
    assert await identity.service.get_email(second) == EMAIL


async def test_concurrent_verification_reserves_one_user(
    identity: Identity, monkeypatch: pytest.MonkeyPatch
) -> None:
    await identity.service.sign_in_with_email(EMAIL)
    original_get = identity.sign_in_codes.get
    original_save = identity.users.save
    ready = asyncio.Event()
    reads = 0
    saved_ids: set[str] = set()

    async def synchronized_get(id: str) -> SignInCode | None:
        nonlocal reads
        document = await original_get(id)
        reads += 1
        if reads <= 2:
            if reads == 2:
                ready.set()
            await ready.wait()
        return document

    async def record_save(user: User) -> None:
        saved_ids.add(user.id)
        await original_save(user)

    monkeypatch.setattr(identity.sign_in_codes, "get", synchronized_get)
    monkeypatch.setattr(identity.users, "save", record_save)
    async with asyncio.timeout(5):
        results = await asyncio.gather(
            identity.service.verify_sign_in_code(EMAIL, identity.email.last_code),
            identity.service.verify_sign_in_code(EMAIL, identity.email.last_code),
            return_exceptions=True,
        )

    assert len(saved_ids) == 1
    assert sum(isinstance(result, InvalidCode) for result in results) == 1
    assert sum(not isinstance(result, BaseException) for result in results) == 1
    sign_in = await original_get(SignInCode.id_for(EMAIL))
    assert sign_in is not None
    assert saved_ids == {str(sign_in.user_id)}
    assert sign_in.challenge is None


@pytest.mark.parametrize("failure_stage", ["create_user", "consume_challenge"])
async def test_verification_resumes_reserved_user_after_write_failure(
    identity: Identity, monkeypatch: pytest.MonkeyPatch, failure_stage: str
) -> None:
    await identity.service.sign_in_with_email(EMAIL)
    original_user_save = identity.users.save
    original_code_save = identity.sign_in_codes.save

    async def fail_user_save(user: User) -> None:
        raise httpx.ConnectError("simulated unavailable database")

    async def fail_consumption(sign_in: SignInCode) -> None:
        if sign_in.challenge is None:
            raise httpx.ConnectError("simulated unavailable database")
        await original_code_save(sign_in)

    if failure_stage == "create_user":
        monkeypatch.setattr(identity.users, "save", fail_user_save)
    else:
        monkeypatch.setattr(identity.sign_in_codes, "save", fail_consumption)
    with pytest.raises(httpx.ConnectError):
        await identity.service.verify_sign_in_code(EMAIL, identity.email.last_code)

    reserved = await identity.sign_in_codes.get(SignInCode.id_for(EMAIL))
    assert reserved is not None
    assert reserved.user_id is not None
    assert reserved.challenge is not None
    monkeypatch.setattr(identity.users, "save", original_user_save)
    monkeypatch.setattr(identity.sign_in_codes, "save", original_code_save)
    pair = await identity.service.verify_sign_in_code(EMAIL, identity.email.last_code)
    claims = identity.verifier.verify(pair.access_token, TokenPurpose.ACCESS)
    assert claims.id == reserved.user_id


@pytest.mark.parametrize("anonymous", [False, True])
async def test_refresh_reuse_and_concurrency_are_supported(
    identity: Identity, anonymous: bool
) -> None:
    if anonymous:
        pair = await identity.service.sign_in_anonymously()
    else:
        await identity.service.sign_in_with_email(EMAIL)
        pair = await identity.service.verify_sign_in_code(
            EMAIL, identity.email.last_code
        )
    results = await asyncio.gather(
        *(identity.service.refresh_token_pair(pair.refresh_token) for _ in range(5))
    )
    assert len({result.refresh_token for result in results}) == 5
    for result in results:
        await identity.service.authorize(
            identity.verifier.verify(result.access_token, TokenPurpose.ACCESS)
        )
        await identity.service.refresh_token_pair(result.refresh_token)


async def test_monthly_refresh_extends_expiry(
    identity: Identity, monkeypatch: pytest.MonkeyPatch
) -> None:
    pair = await identity.service.sign_in_anonymously()
    start = datetime.now(UTC)
    current = start

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls.fromtimestamp(current.timestamp(), tz=tz)

    monkeypatch.setattr("digestify_api.identity.token.datetime", Clock)
    monkeypatch.setattr("jwt.api_jwt.datetime", Clock)
    for month in range(1, 14):
        current = start + timedelta(days=30 * month)
        pair = await identity.service.refresh_token_pair(pair.refresh_token)
        payload = jwt.decode(
            pair.refresh_token, SECRET, algorithms=["HS256"], audience=TOKEN_AUDIENCE
        )
        assert payload["exp"] == int((current + timedelta(days=45)).timestamp())
    current += timedelta(days=46)
    with pytest.raises(jwt.ExpiredSignatureError):
        await identity.service.refresh_token_pair(pair.refresh_token)


async def test_concurrent_wrong_codes_preserve_attempt_budget(
    identity: Identity, monkeypatch: pytest.MonkeyPatch
) -> None:
    await identity.service.sign_in_with_email(EMAIL)
    wrong = "000000" if identity.email.last_code != "000000" else "999999"
    original_get = identity.sign_in_codes.get
    ready = asyncio.Event()
    reads = 0

    async def synchronized_get(id: str) -> SignInCode | None:
        nonlocal reads
        document = await original_get(id)
        reads += 1
        if reads <= 5:
            if reads == 5:
                ready.set()
            await ready.wait()
        return document

    monkeypatch.setattr(identity.sign_in_codes, "get", synchronized_get)
    async with asyncio.timeout(5):
        results = await asyncio.gather(
            *(identity.service.verify_sign_in_code(EMAIL, wrong) for _ in range(5)),
            return_exceptions=True,
        )
    assert all(isinstance(result, InvalidCode) for result in results)
    sign_in = await original_get(SignInCode.id_for(EMAIL))
    assert sign_in is not None and sign_in.challenge is not None
    assert sign_in.challenge.attempts_remaining == 0
    with pytest.raises(InvalidCode):
        await identity.service.verify_sign_in_code(EMAIL, identity.email.last_code)


def test_replica_reservations_agree_across_account_generations() -> None:
    first = SignInCode.for_email(EMAIL)
    second = SignInCode.for_email("  ALICE@EXAMPLE.COM ")
    first_id = first.reserve_user()
    assert second.reserve_user() == first_id
    replacement = first.reserve_user()
    assert replacement != first_id
    assert second.reserve_user() == replacement
    assert SignInCode.for_email("bob@example.com").reserve_user() != first_id


async def test_visible_account_conflict_blocks_authorization_and_refresh(
    identity: Identity,
) -> None:
    await identity.service.sign_in_with_email(EMAIL)
    pair = await identity.service.verify_sign_in_code(EMAIL, identity.email.last_code)
    claims = identity.verifier.verify(pair.access_token, TokenPurpose.ACCESS)
    assert identity.couch is not None
    identity.couch.docs[str(claims.id)]["_conflicts"] = ["2-deleted-branch"]
    with pytest.raises(UnresolvedDocumentConflict):
        await identity.service.authorize(claims)
    with pytest.raises(UnresolvedDocumentConflict):
        await identity.service.refresh_token_pair(pair.refresh_token)


async def test_visible_challenge_conflict_blocks_issue_and_verification(
    identity: Identity,
) -> None:
    await identity.service.sign_in_with_email(EMAIL)
    assert identity.couch is not None
    identity.couch.docs[SignInCode.id_for(EMAIL)]["_conflicts"] = ["2-other"]
    with pytest.raises(UnresolvedDocumentConflict):
        await identity.service.verify_sign_in_code(EMAIL, identity.email.last_code)
    with pytest.raises(UnresolvedDocumentConflict):
        await identity.service.sign_in_with_email(EMAIL)
    assert len(identity.email.sent) == 1
    assert not any(doc["type"] == "user" for doc in identity.couch.docs.values())
