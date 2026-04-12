from typing import Literal
from uuid import UUID

from digestify_api.infrastructure import Command, Entity, Event


class ClaimUsername(Command):
    type: Literal["ClaimUsername"] = "ClaimUsername"
    username: str
    user_id: UUID


class UsernameClaimed(Event):
    type: Literal["UsernameClaimed"] = "UsernameClaimed"
    username: str
    user_id: UUID


class UsernameClaim(Entity):
    type: Literal["UsernameClaim"] = "UsernameClaim"
    claimed_by: UUID

    @staticmethod
    def claim_username(command: ClaimUsername) -> UsernameClaimed:
        return UsernameClaimed(
            entity_id=command.username,
            entity_version=1,
            username=command.username,
            user_id=command.user_id,
        )

    def apply_username_claimed(self, event: UsernameClaimed) -> None:
        self.claimed_by = event.user_id
        self.version = event.entity_version
