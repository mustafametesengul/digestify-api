from uuid import uuid4

from digestify_api.identity.user import User


def test_create_builds_active_user() -> None:
    user_id = uuid4()

    user = User.create(user_id, "alice@example.com")

    assert user.id == str(user_id)
    assert user.email == "alice@example.com"
    assert user.is_deleted is False
    assert user.rev is None


def test_delete_marks_user_deleted() -> None:
    user = User.create(uuid4(), "alice@example.com")

    user.delete()

    assert user.is_deleted is True


def test_revoke_tokens_changes_generation_without_changing_account() -> None:
    user = User.create(uuid4(), "alice@example.com")
    previous = user.token_generation
    user.revoke_tokens()
    assert user.token_generation != previous
    assert user.email == "alice@example.com"
    assert user.is_deleted is False


def test_round_trips_through_couchdb_document_shape() -> None:
    user = User.create(uuid4(), "alice@example.com")
    user.rev = "1-x"

    stored = user.model_dump(by_alias=True, mode="json")
    loaded = User.model_validate(stored)

    assert loaded == user
