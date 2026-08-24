from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from digestify_api.identity.sign_in_code import (
    CODE_LENGTH,
    CODE_TIME_TO_LIVE,
    ISSUE_COOLDOWN,
    MAX_VERIFICATION_ATTEMPTS,
    CodeRequestedTooSoon,
    InvalidCode,
    SignInCode,
)

NOW = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)


def wrong_code(code: str) -> str:
    return "000000" if code != "000000" else "999999"


def test_for_email_normalizes_address() -> None:
    sign_in = SignInCode.for_email("  Alice@Example.COM ")

    assert sign_in.email == "alice@example.com"
    assert sign_in.id == SignInCode.id_for("alice@example.com")


def test_id_for_normalizes_address() -> None:
    assert SignInCode.id_for(" Alice@Example.COM ") == SignInCode.id_for(
        "alice@example.com"
    )


def test_issue_arms_a_challenge() -> None:
    sign_in = SignInCode.for_email("alice@example.com")

    code = sign_in.issue(NOW)

    assert len(code) == CODE_LENGTH
    assert code.isdigit()
    assert sign_in.last_issued_at == NOW
    assert sign_in.challenge is not None
    assert sign_in.challenge.expires_at == NOW + CODE_TIME_TO_LIVE
    assert sign_in.challenge.attempts_remaining == MAX_VERIFICATION_ATTEMPTS


def test_issue_within_cooldown_keeps_outstanding_challenge() -> None:
    sign_in = SignInCode.for_email("alice@example.com")
    code = sign_in.issue(NOW)

    with pytest.raises(CodeRequestedTooSoon):
        sign_in.issue(NOW + ISSUE_COOLDOWN - timedelta(seconds=1))

    sign_in.verify(code, NOW + timedelta(seconds=59))


def test_issue_after_cooldown_replaces_challenge() -> None:
    sign_in = SignInCode.for_email("alice@example.com")
    sign_in.issue(NOW)

    later = NOW + ISSUE_COOLDOWN
    code = sign_in.issue(later)

    sign_in.verify(code, later + timedelta(minutes=1))
    assert sign_in.last_issued_at == later


def test_verify_accepts_correct_code_and_keeps_attempts() -> None:
    sign_in = SignInCode.for_email("alice@example.com")
    code = sign_in.issue(NOW)

    sign_in.verify(code, NOW + timedelta(minutes=1))

    assert sign_in.challenge is not None
    assert sign_in.challenge.attempts_remaining == MAX_VERIFICATION_ATTEMPTS


def test_verify_wrong_code_consumes_an_attempt() -> None:
    sign_in = SignInCode.for_email("alice@example.com")
    code = sign_in.issue(NOW)

    with pytest.raises(InvalidCode):
        sign_in.verify(wrong_code(code), NOW + timedelta(minutes=1))

    assert sign_in.challenge is not None
    assert sign_in.challenge.attempts_remaining == MAX_VERIFICATION_ATTEMPTS - 1


def test_verify_without_challenge_fails() -> None:
    sign_in = SignInCode.for_email("alice@example.com")

    with pytest.raises(InvalidCode):
        sign_in.verify("123456", NOW)


def test_verify_expired_challenge_fails() -> None:
    sign_in = SignInCode.for_email("alice@example.com")
    code = sign_in.issue(NOW)

    with pytest.raises(InvalidCode):
        sign_in.verify(code, NOW + CODE_TIME_TO_LIVE)


def test_verify_exhausted_challenge_rejects_even_correct_code() -> None:
    sign_in = SignInCode.for_email("alice@example.com")
    code = sign_in.issue(NOW)
    later = NOW + timedelta(minutes=1)

    for _ in range(MAX_VERIFICATION_ATTEMPTS):
        with pytest.raises(InvalidCode):
            sign_in.verify(wrong_code(code), later)

    with pytest.raises(InvalidCode):
        sign_in.verify(code, later)


def test_link_user_consumes_challenge() -> None:
    sign_in = SignInCode.for_email("alice@example.com")
    code = sign_in.issue(NOW)
    user_id = uuid4()

    sign_in.link_user(user_id)

    assert sign_in.user_id == user_id
    assert sign_in.challenge is None
    with pytest.raises(InvalidCode):
        sign_in.verify(code, NOW + timedelta(minutes=1))


def test_round_trips_through_couchdb_document_shape() -> None:
    sign_in = SignInCode.for_email("alice@example.com")
    sign_in.user_id = uuid4()
    sign_in.issue(NOW)
    sign_in.rev = "1-x"

    stored = sign_in.model_dump(by_alias=True, mode="json")
    loaded = SignInCode.model_validate(stored)

    assert loaded == sign_in
