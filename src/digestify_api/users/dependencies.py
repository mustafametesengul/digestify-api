from typing import Annotated

from fastapi import Depends

from digestify_api.db import DBService, get_db
from digestify_api.users.service import UserService


def get_user_service(db: Annotated[DBService, Depends(get_db)]) -> UserService:
    return UserService(db)
