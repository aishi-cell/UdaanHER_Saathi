from functools import lru_cache

from langchain_openai import ChatOpenAI

from app.config import get_settings


@lru_cache(maxsize=8)
def _cached_chat_model(model: str, api_key: str, temperature: float) -> ChatOpenAI:
    return ChatOpenAI(model=model, api_key=api_key, temperature=temperature)


def get_chat_model(temperature: float = 0.7) -> ChatOpenAI:
    """Factory for the agent nodes' LLM client. Conversational nodes (T12)
    should use the default temperature; grading nodes (T19) should pass
    <= 0.2 per Spec S6.3.

    Instances are cached per (model, key, temperature): every agent node
    calls this per LLM call, and rebuilding the client each time meant a
    fresh connection pool per call (~100-300ms measured overhead, T24).
    """
    settings = get_settings()
    return _cached_chat_model(settings.openai_model, settings.openai_api_key, temperature)
