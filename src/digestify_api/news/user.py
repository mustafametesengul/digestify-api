from typing import Literal

from digestify_api.infrastructure.couchdb import Document


class User(Document):
    """A `news`-local projection of an `identity` user.

    Built by replaying identity's `_changes` feed; news deliberately keeps only
    what it needs and never sees identity-owned fields such as the email.
    """

    type: Literal["user"] = "user"
    is_deleted: bool = False

    def is_active(self) -> bool:
        return not self.is_deleted
