from uuid import UUID

from pydantic import BaseModel


class Auth(BaseModel):
    id: UUID
    is_anonymous: bool
