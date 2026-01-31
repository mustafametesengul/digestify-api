from digestify_api.core import OpenAI, OpenAISettings

_openai: OpenAI | None = None


def init_openai(settings: OpenAISettings) -> OpenAI:
    global _openai
    _openai = OpenAI(settings)
    return _openai


def get_openai() -> OpenAI:
    if _openai is None:
        raise RuntimeError("OpenAI client not initialized")
    return _openai
