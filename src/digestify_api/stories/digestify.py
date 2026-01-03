from datetime import datetime

from openai import AsyncOpenAI
from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Topic(BaseModel):
    name: str
    description: str


class Story(BaseModel):
    title: str
    content: str
    published_at: str
    reference_urls: list[str]


class Digest(BaseModel):
    stories: list[Story]


class DigestifySettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    webquest_mcp_api_key: SecretStr = Field(default=...)
    webquest_mcp_url: str = Field(default=...)
    max_tool_calls: int = Field(default=5)
    max_output_tokens: int = Field(default=100000)
    openai_api_key: SecretStr = Field(default=...)


class Digestify:
    def __init__(
        self,
        settings: DigestifySettings | None = None,
        openai_client: AsyncOpenAI | None = None,
    ) -> None:
        if settings is None:
            settings = DigestifySettings()
        self._settings = settings

        openai_api_key = self._settings.openai_api_key.get_secret_value()
        if openai_client is None:
            openai_client = AsyncOpenAI(api_key=openai_api_key)
        self._openai_client = openai_client

    async def get_stories(self, topic: Topic) -> Digest:
        webquest_mcp_api_key = self._settings.webquest_mcp_api_key.get_secret_value()
        today = datetime.now().strftime("%Y-%m-%d")
        prompt = (
            f"Today is {today}.\n"
            f"Get the latest updates about the following topic:\n"
            f"{topic.model_dump_json()}\n"
            "If the topic is about a content creator, focus on their latest content. "
            "When creating queries, don't put things like 'latest news' "
            "or 'today' as input. Just use the topic name. "
            "If you see YouTube links, "
            "make sure to use the transcript tool to get details from latest videos."
        )

        response = await self._openai_client.responses.parse(
            model="gpt-5.2",
            max_tool_calls=self._settings.max_tool_calls,
            max_output_tokens=self._settings.max_output_tokens,
            tools=[
                {
                    "type": "mcp",
                    "server_label": "webquest_mcp",
                    "server_url": self._settings.webquest_mcp_url,
                    "require_approval": "never",
                    "headers": {"Authorization": f"Bearer {webquest_mcp_api_key}"},
                },
            ],
            input=prompt,
            text_format=Digest,
        )

        result = response.output_parsed
        if result is None:
            raise ValueError("Failed to parse response")

        return result
