from digestify_api.queries.follows import create_follow, read_follow, update_follow
from digestify_api.queries.migrations import (
    create_initial_tables,
    create_schema_migrations_table,
    get_applied_migrations,
    reset_db,
    update_schema_migrations,
)
from digestify_api.queries.stories import (
    create_story,
    read_stories_by_topic,
    read_story,
    story_exists,
)
from digestify_api.queries.tasks import (
    create_task,
    get_pending_tasks,
    mark_task_completed,
    mark_task_failed,
    mark_task_in_progress,
    read_task,
    update_task,
)
from digestify_api.queries.topics import (
    create_topic,
    decrement_followers_count,
    increment_followers_count,
    read_topic,
    topic_exists,
)
from digestify_api.queries.users import (
    create_user,
    decrement_followed_topics_count,
    increment_created_topics_count,
    increment_followed_topics_count,
    read_user,
    update_user,
    user_exists,
)

__all__ = [
    "create_follow",
    "update_follow",
    "create_user",
    "update_user",
    "user_exists",
    "increment_followed_topics_count",
    "read_follow",
    "read_user",
    "decrement_followers_count",
    "increment_followers_count",
    "read_topic",
    "create_topic",
    "topic_exists",
    "create_task",
    "read_task",
    "update_task",
    "get_pending_tasks",
    "mark_task_in_progress",
    "mark_task_completed",
    "mark_task_failed",
    "decrement_followed_topics_count",
    "increment_created_topics_count",
    "create_story",
    "read_story",
    "story_exists",
    "read_stories_by_topic",
    "create_initial_tables",
    "create_schema_migrations_table",
    "get_applied_migrations",
    "reset_db",
    "update_schema_migrations",
]
