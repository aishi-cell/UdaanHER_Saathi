from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from app.services.llm import get_chat_model

PROMPTS_DIR = Path(__file__).parent / "prompts"

T = TypeVar("T", bound=BaseModel)

# Below this, STT almost certainly returned noise/silence rather than a real
# answer (a single stray syllable, background noise misheard as a word).
# Nodes check this before attempting structured extraction, so an unclear
# answer gets a warm re-ask instead of a hallucinated/garbage extraction.
MIN_USABLE_TRANSCRIPT_LENGTH = 2


def is_unclear(transcript: str) -> bool:
    return len((transcript or "").strip()) < MIN_USABLE_TRANSCRIPT_LENGTH


def load_prompt(name: str, *, language: str, instruction: str) -> str:
    template = (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    return template.format(language=language, instruction=instruction)


async def ask_conversational(
    prompt_name: str, *, language: str, instruction: str, transcript: str
) -> str:
    """One short (2-3 sentence) in-character reply in the session language."""
    system = load_prompt(prompt_name, language=language, instruction=instruction)
    llm = get_chat_model(temperature=0.7)
    # "(no speech was heard clearly)" rather than framing this as the start
    # of the conversation -- that framing is only correct for the true
    # first turn (greet's step0, which passes "" deliberately and whose
    # instruction is self-contained regardless). Everywhere else, an empty
    # transcript means her speech didn't come through, not that nothing has
    # happened yet.
    response = await llm.ainvoke(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": transcript or "(no speech was heard clearly)"},
        ]
    )
    return str(response.content).strip()


async def extract_structured(
    prompt_name: str,
    *,
    language: str,
    instruction: str,
    transcript: str,
    schema: type[T],
) -> T:
    """A structured-output call bound to a Pydantic model -- never prose parsing."""
    system = load_prompt(prompt_name, language=language, instruction=instruction)
    llm = get_chat_model(temperature=0.2).with_structured_output(schema)
    result = await llm.ainvoke(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": transcript},
        ]
    )
    return result  # type: ignore[return-value]
