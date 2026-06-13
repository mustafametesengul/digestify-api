from pydantic import BaseModel


class User(BaseModel):
    is_deleted: bool
