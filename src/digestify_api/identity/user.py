from typing import Literal, Self


from digestify_api.infrastructure import Entity, Message, Repository


class UserSignedUp(Message):
    type: Literal["UserSignedUp"] = "UserSignedUp"


class AccountDeleted(Message):
    type: Literal["AccountDeleted"] = "AccountDeleted"


class User(Entity):
    type: Literal["User"] = "User"
    username: str | None
    password_hash: str | None

    @classmethod
    def create_with_username_and_password(
        cls,
        username: str,
        password_hash: str,
    ) -> Self:
        user = cls(
            username=username,
            password_hash=password_hash,
        )
        user.add_to_outbox(UserSignedUp())
        return user

    def delete_account(self) -> None:
        self.mark_as_discarded()
        self.add_to_outbox(AccountDeleted())


class UserRepository(Repository[User]):
    async def find_by_username(self, username: str) -> User | None:
        document = await self._collection.find_one(
            {"username": username, "is_deleted": False}
        )
        if document is None:
            return None
        return User.model_validate(document)

    async def create_indices(self) -> None:
        await self._collection.create_index("username", unique=True, sparse=True)
