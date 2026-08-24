from uuid import UUID

from digestify_api.quota import QuotaService
from digestify_api.topic import Language, TopicService


class TopicManager:
    def __init__(
        self,
        topic_service: TopicService,
        quota_service: QuotaService,
    ) -> None:
        self._topic_service = topic_service
        self._quota_service = quota_service

    async def init(self) -> None:
        await self._topic_service.init()
        await self._quota_service.init()

    async def create(
        self,
        topic_id: UUID,
        user_id: UUID,
        name: str,
        description: str,
        language: Language,
    ) -> None:
        await self._topic_service.create(
            topic_id=topic_id,
            user_id=user_id,
            name=name,
            description=description,
            language=language,
        )
        await self._quota_service.activate_topic(user_id, topic_id)

    async def delete(self, topic_id: UUID, user_id: UUID) -> None:
        await self._quota_service.deactivate_topic(user_id, topic_id)
        await self._topic_service.delete(topic_id)
