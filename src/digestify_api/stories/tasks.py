from digestify import Digestify

from digestify_api.db import get_db
from digestify_api.stories.models import GetStories
from digestify_api.stories.service import StoryService
from digestify_api.tasks import TaskRouter

router = TaskRouter()


@router.register_handler
async def get_stories(payload: GetStories) -> None:
    print(f"Handling example task with payload: {payload}")
    db = get_db()
    digestify = Digestify()
    story_service = StoryService(db, digestify)
    await story_service.save_stories_by_topic(payload.topic_id)
