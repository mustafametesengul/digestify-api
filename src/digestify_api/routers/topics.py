from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from digestify_api.core import DBManager, from_handler
from digestify_api.dependencies import get_auth, get_db, get_openai
from digestify_api.exceptions import (
    TopicAlreadyExists,
    TopicContainsInappropriateContent,
    TopicLimitExceeded,
    UserNotFound,
)
from digestify_api.models import (
    Auth,
    Follow,
    Language,
    StoryTaskPayload,
    SubscriptionTier,
    Topic,
    TopicPublic,
)
from digestify_api.queries import (
    create_follow,
    create_task,
    create_topic,
    increment_created_topics_count,
    read_user,
    topic_exists,
)
from digestify_api.tasks import save_stories_by_topic

topics_router = APIRouter(
    prefix="/topics",
    tags=["topics"],
)


@topics_router.post("/create", status_code=201)
async def create(
    auth: Annotated[Auth, Depends(get_auth)],
    db: Annotated[DBManager, Depends(get_db)],
    topic_id: UUID,
    name: str,
    description: str,
    language: Language,
    image_url: str | None = None,
) -> TopicPublic:
    now = datetime.now(timezone.utc)

    openai = get_openai()

    openai_input = f"{name}\n\n{description}"
    response = await openai.moderations.create(
        model="omni-moderation-latest",
        input=openai_input,
    )
    flagged = response.results[0].flagged

    if flagged:
        raise TopicContainsInappropriateContent()

    response = await openai.embeddings.create(
        input=openai_input, model="text-embedding-3-small"
    )
    embedding = str(response.data[0].embedding)

    async with db.get_connection() as connection:
        user = await read_user(connection, auth.id)
        if user is None:
            raise UserNotFound()

        topic_exists_flag = await topic_exists(connection, topic_id)
        if topic_exists_flag:
            raise TopicAlreadyExists()

        if (
            user.created_topics_count >= 5
            and user.subscription_tier is SubscriptionTier.FREE
        ):
            raise TopicLimitExceeded(
                detail=(
                    "Free tier users can create up to 5 topics. "
                    "Please upgrade your subscription to create topics."
                )
            )

        if (
            user.created_topics_count >= 10
            and user.subscription_tier is SubscriptionTier.PREMIUM
        ):
            raise TopicLimitExceeded(
                detail=(
                    "Premium tier users can create up to 10 topics. "
                    "Please delete some topics to create new ones."
                )
            )

        await increment_created_topics_count(connection, auth.id)

        topic = Topic(
            id=topic_id,
            user_id=auth.id,
            discarded=False,
            image_url=image_url,
            is_active=True,
            name=name,
            description=description,
            language=language,
            followers_count=1,
            created_at=now,
            updated_at=None,
            embedding=embedding,
        )

        await create_topic(connection, topic)

        follow = Follow(
            user_id=auth.id,
            topic_id=topic_id,
            is_following=True,
            created_at=now,
            updated_at=None,
        )

        await create_follow(connection, follow)

        task = from_handler(
            save_stories_by_topic,
            StoryTaskPayload(
                topic_id=topic_id,
            ),
            created_at=now,
        )
        await create_task(connection, task)
        return TopicPublic.model_validate(topic)
