from openai import AsyncOpenAI
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class OpenAISettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_prefix="OPENAI_",
    )

    api_key: SecretStr = Field(...)


class OpenAI:
    def __init__(self, settings: OpenAISettings) -> None:
        self._client = AsyncOpenAI(api_key=settings.api_key.get_secret_value())

    async def get_embeddings(self, texts: list[str]) -> list[str]:
        response = await self._client.embeddings.create(
            input=texts, model="text-embedding-3-small"
        )
        embeddings = [str(data.embedding) for data in response.data]
        return embeddings

    async def check_for_moderation(self, texts: list[str]) -> list[bool]:
        response = await self._client.moderations.create(
            model="omni-moderation-latest",
            input=texts,
        )
        flagged_list = [result.flagged for result in response.results]
        return flagged_list
