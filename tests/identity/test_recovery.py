import asyncio
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from digestify_api.couchdb import WriteNotConfirmed
from digestify_api.identity.sign_in_code import InvalidCode, SignInCode
from digestify_api.identity.token import TokenPair, TokenPurpose
from digestify_api.identity.user import User
from tests.identity.test_service import EMAIL, Identity
from tests.identity.test_service import identity as identity


async def issue_pair(identity: Identity, email: str = EMAIL) -> TokenPair:
    await identity.reset_cooldown(email)
    await identity.service.sign_in_with_email(email)
    return await identity.service.verify_sign_in_code(email, identity.email.last_code)


async def recovery_code(identity: Identity) -> str:
    await identity.reset_cooldown()
    await identity.service.sign_in_with_email(EMAIL)
    return identity.email.last_code


async def test_recovery_revokes_all_old_tokens_but_preserves_account(
    identity: Identity,
) -> None:
    first = await issue_pair(identity)
    second = await issue_pair(identity)
    unrelated = await issue_pair(identity, "bob@example.com")
    old_claims = identity.verifier.verify(first.access_token, TokenPurpose.ACCESS)
    second_claims = identity.verifier.verify(second.access_token, TokenPurpose.ACCESS)
    assert second_claims.token_generation == old_claims.token_generation
    code = await recovery_code(identity)
    recovered = await identity.service.verify_sign_in_code(
        EMAIL, code, revoke_tokens=True
    )
    new_claims = identity.verifier.verify(recovered.access_token, TokenPurpose.ACCESS)
    assert new_claims.id == old_claims.id
    assert new_claims.token_generation != old_claims.token_generation

    for pair in (first, second):
        claims = identity.verifier.verify(pair.access_token, TokenPurpose.ACCESS)
        with pytest.raises(jwt.InvalidTokenError):
            await identity.service.authorize(claims)
        with pytest.raises(jwt.InvalidTokenError):
            await identity.service.get_email(claims)
        with pytest.raises(jwt.InvalidTokenError):
            await identity.service.delete_account(claims)
        with pytest.raises(jwt.InvalidTokenError):
            await identity.service.refresh_token_pair(pair.refresh_token)

    assert await identity.service.get_email(new_claims) == EMAIL
    renewed = await identity.service.refresh_token_pair(recovered.refresh_token)
    renewed_claims = identity.verifier.verify(renewed.access_token, TokenPurpose.ACCESS)
    assert renewed_claims.token_generation == new_claims.token_generation
    await identity.service.authorize(renewed_claims)
    await identity.service.refresh_token_pair(unrelated.refresh_token)
    with pytest.raises(InvalidCode):
        await identity.service.verify_sign_in_code(EMAIL, code, revoke_tokens=True)


@pytest.mark.parametrize("invalid", ["wrong", "expired", "consumed"])
async def test_recovery_requires_live_email_code(
    identity: Identity, invalid: str
) -> None:
    pair = await issue_pair(identity)
    code = await recovery_code(identity)
    if invalid == "wrong":
        code = "000000" if code != "000000" else "999999"
    elif invalid == "expired":
        sign_in = await identity.sign_in_codes.get(SignInCode.id_for(EMAIL))
        assert sign_in is not None and sign_in.challenge is not None
        sign_in.challenge.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await identity.sign_in_codes.save(sign_in)
    else:
        await identity.service.verify_sign_in_code(EMAIL, code)
    with pytest.raises(InvalidCode):
        await identity.service.verify_sign_in_code(EMAIL, code, revoke_tokens=True)
    await identity.service.refresh_token_pair(pair.refresh_token)


@pytest.mark.parametrize("committed", [False, True])
async def test_unconfirmed_recovery_returns_no_tokens_and_can_be_retried_with_new_code(
    identity: Identity, monkeypatch: pytest.MonkeyPatch, committed: bool
) -> None:
    pair = await issue_pair(identity)
    code = await recovery_code(identity)
    original_save = identity.users.save

    async def uncertain_save(user: User) -> None:
        if committed:
            await original_save(user)
        raise WriteNotConfirmed(user.id)

    monkeypatch.setattr(identity.users, "save", uncertain_save)
    with pytest.raises(WriteNotConfirmed):
        await identity.service.verify_sign_in_code(EMAIL, code, revoke_tokens=True)
    with pytest.raises(InvalidCode):
        await identity.service.verify_sign_in_code(EMAIL, code, revoke_tokens=True)
    monkeypatch.setattr(identity.users, "save", original_save)
    if committed:
        with pytest.raises(jwt.InvalidTokenError):
            await identity.service.refresh_token_pair(pair.refresh_token)
    fresh_code = await recovery_code(identity)
    recovered = await identity.service.verify_sign_in_code(
        EMAIL, fresh_code, revoke_tokens=True
    )
    await identity.service.refresh_token_pair(recovered.refresh_token)
    with pytest.raises(jwt.InvalidTokenError):
        await identity.service.refresh_token_pair(pair.refresh_token)


async def test_concurrent_recovery_consumes_code_once(
    identity: Identity, monkeypatch: pytest.MonkeyPatch
) -> None:
    await issue_pair(identity)
    code = await recovery_code(identity)
    original_get = identity.sign_in_codes.get
    ready = asyncio.Event()
    reads = 0

    async def synchronized_get(id: str) -> SignInCode | None:
        nonlocal reads
        sign_in = await original_get(id)
        reads += 1
        if reads <= 2:
            if reads == 2:
                ready.set()
            await ready.wait()
        return sign_in

    monkeypatch.setattr(identity.sign_in_codes, "get", synchronized_get)
    async with asyncio.timeout(5):
        results = await asyncio.gather(
            *(
                identity.service.verify_sign_in_code(EMAIL, code, revoke_tokens=True)
                for _ in range(2)
            ),
            return_exceptions=True,
        )
    assert sum(isinstance(result, InvalidCode) for result in results) == 1
    pairs = [result for result in results if isinstance(result, TokenPair)]
    assert len(pairs) == 1
    await identity.service.refresh_token_pair(pairs[0].refresh_token)


async def test_inflight_refresh_never_upgrades_old_generation(
    identity: Identity, monkeypatch: pytest.MonkeyPatch
) -> None:
    pair = await issue_pair(identity)
    code = await recovery_code(identity)
    original_get = identity.users.get
    observed = asyncio.Event()
    resume = asyncio.Event()

    async def stale_get(id: str) -> User | None:
        user = await original_get(id)
        if not observed.is_set():
            observed.set()
            await resume.wait()
        return user

    monkeypatch.setattr(identity.users, "get", stale_get)
    async with asyncio.timeout(5):
        async with asyncio.TaskGroup() as tasks:
            refresh = tasks.create_task(
                identity.service.refresh_token_pair(pair.refresh_token)
            )
            await observed.wait()
            try:
                await identity.service.verify_sign_in_code(
                    EMAIL, code, revoke_tokens=True
                )
            finally:
                resume.set()
    stale_pair = refresh.result()
    with pytest.raises(jwt.InvalidTokenError):
        await identity.service.refresh_token_pair(stale_pair.refresh_token)
