from functools import lru_cache

from langchain_openai import ChatOpenAI

from app.config import get_settings


@lru_cache(maxsize=8)
def _cached_chat_model(model: str, api_key: str, temperature: float) -> ChatOpenAI:
    # max_retries covers transient network blips (live phone test: a brief
    # DNS failure 500'd three turns in a row); the SDK backs off between
    # attempts, so a short outage costs seconds, not the turn.
    return ChatOpenAI(model=model, api_key=api_key, temperature=temperature, max_retries=4)


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


async def describe_practice_photo(image_bytes: bytes, mime_type: str) -> str:
    """Vision pass for practice review: neutral, concrete observations that
    the practice node then turns into warm pedagogy. Kept separate so the
    node never sees raw pixels and the vision prompt never does teaching."""
    import base64

    data_uri = f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode()}"
    llm = get_chat_model(temperature=0.2)
    response = await llm.ainvoke(
        [
            {
                "role": "system",
                "content": (
                    "You examine a photo of a learner's vocational practice work "
                    "(stitch lines, mehndi on a hand or paper, a pickle jar setup, "
                    "measurements being taken, etc.). Describe concretely and "
                    "neutrally in English what is visible and any quality cues -- "
                    "line steadiness, spacing, symmetry, tension, cleanliness, "
                    "setup. 3-5 short bullet points. Purely observational: no "
                    "judgement words like bad, wrong, poor."
                ),
            },
            {
                "role": "user",
                "content": [{"type": "image_url", "image_url": {"url": data_uri}}],
            },
        ]
    )
    return str(response.content).strip()
