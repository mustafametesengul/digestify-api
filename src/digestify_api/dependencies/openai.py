from openai import AsyncOpenAI

from digestify_api.core.openai import OpenAISettings

_openai: AsyncOpenAI | None = None


def init_openai(settings: OpenAISettings) -> AsyncOpenAI:
    global _openai
    _openai = AsyncOpenAI(api_key=settings.api_key.get_secret_value())
    return _openai


def get_openai() -> AsyncOpenAI:
    if _openai is None:
        raise RuntimeError("OpenAI client not initialized")
    return _openai
