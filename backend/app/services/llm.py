from langchain_openai import ChatOpenAI

from app.config import get_settings


def get_chat_model(temperature: float = 0.7) -> ChatOpenAI:
    """Factory for the agent nodes' LLM client. Conversational nodes (T12)
    should use the default temperature; grading nodes (T19) should pass
    <= 0.2 per Spec S6.3."""
    settings = get_settings()
    return ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=temperature,
    )
