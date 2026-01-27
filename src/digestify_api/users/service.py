from uuid import UUID

from digestify_api.db import DBService
from digestify_api.users.exceptions import UserAlreadyExists
from digestify_api.users.models import SubscriptionTier, UserCreate
from digestify_api.users.repository import UserRepository


class UserService:
    def __init__(self, db: DBService) -> None:
        self._db = db

    async def register(self, user_id: UUID) -> None:
        async with self._db.get_connection() as connection:
            user_repository = UserRepository(connection)

            user_exists = await user_repository.user_exists(user_id)
            if user_exists:
                raise UserAlreadyExists()

            user = UserCreate(
                id=user_id,
                discarded=False,
                subscription_tier=SubscriptionTier.FREE,
                created_topics_count=0,
                followed_topics_count=0,
            )

            await user_repository.create_user(user)
