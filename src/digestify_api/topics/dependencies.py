from typing import Annotated

from fastapi import Depends

from digestify_api.db import DBService, get_db
from digestify_api.topics.service import TopicService


def get_topic_service(db: Annotated[DBService, Depends(get_db)]) -> TopicService:
    return TopicService(db)
