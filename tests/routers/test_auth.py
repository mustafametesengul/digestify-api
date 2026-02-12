import uuid

from httpx import AsyncClient

from digestify_api import dependencies, queries


async def test_sign_up_with_username_creates_user_and_task(
    client: AsyncClient,
    db: dependencies.db.DBManager,
) -> None:
    username = f"user_{uuid.uuid4().hex[:8]}"
    payload = {"username": username, "password": "password123"}

    response = await client.post("/auth/sign_up_with_username", json=payload)
    assert response.status_code == 201

    async with db.get_connection() as connection:
        user = await queries.users.get_by_username(connection, username)
        assert user is not None
        assert user.username == username
        assert user.password_hash is not None
        assert user.tier.value == "free"

        task_row = await connection.fetchrow(
            "SELECT name, status FROM tasks WHERE payload::json->>'user_id' = $1",
            str(user.id),
        )
        assert task_row is not None
        assert task_row["name"] == "check_user_tier"
        assert task_row["status"] == "pending"


async def test_sign_up_with_username_conflict(client: AsyncClient) -> None:
    username = f"user_{uuid.uuid4().hex[:8]}"
    payload = {"username": username, "password": "password123"}

    first = await client.post("/auth/sign_up_with_username", json=payload)
    second = await client.post("/auth/sign_up_with_username", json=payload)

    assert first.status_code == 201
    assert second.status_code == 409


async def test_sign_in_anonymously_returns_tokens(
    client: AsyncClient,
    auth_manager: dependencies.auth.AuthManager,
) -> None:
    response = await client.post("/auth/sign_in_anonymously")
    assert response.status_code == 201
    body = response.json()

    assert body["token_type"] == "Bearer"
    access_auth = auth_manager.verify_jwt_token(
        body["access_token"], token_type="access"
    )
    refresh_auth = auth_manager.verify_jwt_token(
        body["refresh_token"], token_type="refresh"
    )
    assert access_auth.is_anonymous is True
    assert refresh_auth.is_anonymous is True


async def test_sign_in_with_username_success(
    client: AsyncClient,
    auth_manager: dependencies.auth.AuthManager,
) -> None:
    username = f"user_{uuid.uuid4().hex[:8]}"
    password = "password123"

    sign_up = await client.post(
        "/auth/sign_up_with_username",
        json={"username": username, "password": password},
    )
    assert sign_up.status_code == 201

    sign_in = await client.post(
        "/auth/sign_in_with_username",
        json={"username": username, "password": password},
    )
    assert sign_in.status_code == 200

    body = sign_in.json()
    access_auth = auth_manager.verify_jwt_token(
        body["access_token"], token_type="access"
    )
    assert access_auth.is_anonymous is False


async def test_sign_in_with_username_invalid_credentials(client: AsyncClient) -> None:
    username = f"user_{uuid.uuid4().hex[:8]}"
    await client.post(
        "/auth/sign_up_with_username",
        json={"username": username, "password": "password123"},
    )

    response = await client.post(
        "/auth/sign_in_with_username",
        json={"username": username, "password": "wrongpass123"},
    )
    assert response.status_code == 401


async def test_refresh_token_returns_new_tokens(client: AsyncClient) -> None:
    sign_in = await client.post("/auth/sign_in_anonymously")
    refresh_token = sign_in.json()["refresh_token"]

    response = await client.post(
        "/auth/refresh_token",
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "Bearer"
    assert body["access_token"]
    assert body["refresh_token"]
