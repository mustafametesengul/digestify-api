from uuid import UUID

import jwt

from digestify_api.couchdb import Client, Repository
from digestify_api.identity.token import TokenClaims, UserClaims, UserRole
from digestify_api.identity.user import User

DATABASE_NAME = "identity"


class Accounts:
    """Read-only account checks without email or token-signing clients."""

    def __init__(self, client: Client) -> None:
        self._users = Repository(User, client.get_database(DATABASE_NAME))

    async def validate_user(self, user_claims: UserClaims) -> None:
        if user_claims.role is not UserRole.ANONYMOUS:
            await self._get_authorized_user(user_claims)

    async def authorize(self, claims: TokenClaims) -> None:
        """Check account state; revocation propagates with replication."""
        await self.validate_user(claims)

    async def is_active(self, user_id: UUID) -> bool:
        return await self._get_user(user_id) is not None

    async def _get_authorized_user(self, claims: UserClaims) -> User:
        user = await self._get_user(claims.id)
        if (
            user is None
            or claims.role is UserRole.ANONYMOUS
            or claims.token_generation != user.token_generation
        ):
            raise jwt.InvalidTokenError()
        return user

    async def _get_user(self, user_id: UUID) -> User | None:
        user = await self._users.get(str(user_id))
        if user is None or user.is_deleted:
            return None
        return user
