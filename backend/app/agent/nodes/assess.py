"""Real assess node (T12): 3 story-questions, then structured ProfileDraft extraction."""

from typing import Literal

from pydantic import BaseModel

from app.agent.llm_utils import ask_conversational, extract_structured, is_unclear
from app.agent.state import AgentState

MAX_QUESTIONS = 3

QUESTION_INSTRUCTION = (
    "Here is what you already know about her: name {name}, from {village}, "
    "wants to learn {interest}. Do not ask about any of that again -- it's "
    "already been covered.\n\n"
    "Ask her a warm, story-style question about her experience with {interest} "
    "specifically -- something like 'Have you ever tried...' or 'Tell me "
    "about a time you...'. This is question {question_number} of "
    "{max_questions} about her experience with {interest}; if there is a "
    "conversation so far below, build on it and don't repeat a question "
    "already asked.\n\n"
    "Conversation so far:\n{conversation_so_far}"
)
REASK_INSTRUCTION = (
    "You couldn't quite make out her last answer. Warmly and briefly say you "
    "didn't catch that, and ask the same question again in slightly "
    "different, simpler words -- no need to apologise much, this happens."
)
WRAP_INSTRUCTION = (
    "Thank her warmly for sharing, and say you're ready to look at her "
    "profile together next."
)


class LevelExtraction(BaseModel):
    starting_level: Literal["new", "some", "experienced"]
    notes: str


def _append_history(state: AgentState, reply: str) -> list:
    history = list(state.get("history") or [])
    if state["transcript"]:
        history.append({"role": "user", "text": state["transcript"]})
    history.append({"role": "mentor", "text": reply})
    return history[-12:]


def _conversation_so_far(history: list) -> str:
    if not history:
        return "(nothing yet)"
    return "\n".join(f"{h['role']}: {h['text']}" for h in history)


async def run(state: AgentState) -> dict:
    profile = dict(state.get("profile") or {})
    interest = profile.get("interest", "this skill")
    step = state["stage_step"]

    # step 0 is the first question -- nothing assess-specific has been asked
    # yet, so there's no prior answer to have been "unclear." Steps 1+ are
    # processing her answer to the previous question.
    if 0 < step <= MAX_QUESTIONS and is_unclear(state["transcript"]):
        reply = await ask_conversational(
            "assess", language=state["language"], instruction=REASK_INSTRUCTION, transcript=""
        )
        return {"stage": "assess", "stage_step": step, "reply_text": reply, "ui": {"type": "idle"}}

    if step < MAX_QUESTIONS:
        reply = await ask_conversational(
            "assess",
            language=state["language"],
            instruction=QUESTION_INSTRUCTION.format(
                name=profile.get("name", "?"),
                village=profile.get("village", "?"),
                interest=interest,
                question_number=step + 1,
                max_questions=MAX_QUESTIONS,
                conversation_so_far=_conversation_so_far(state.get("history") or []),
            ),
            transcript=state["transcript"],
        )
        return {
            "stage": "assess",
            "stage_step": step + 1,
            "history": _append_history(state, reply),
            "reply_text": reply,
            "ui": {"type": "idle"},
        }

    # step == MAX_QUESTIONS: her answer to the last question just arrived.
    history = list(state.get("history") or [])
    if state["transcript"]:
        history.append({"role": "user", "text": state["transcript"]})
    conversation_so_far = _conversation_so_far(history)

    extraction = await extract_structured(
        "assess",
        language=state["language"],
        instruction=(
            f"Based on the whole conversation so far, judge her starting level "
            f"with {interest} as 'new' (never tried), 'some' (has tried a "
            f"bit), or 'experienced' (comfortable already). Write one short "
            f"note in English summarising what she already seems to know, for "
            f"another mentor to read later.\n\nConversation so far:\n"
            f"{conversation_so_far}"
        ),
        transcript=state["transcript"],
        schema=LevelExtraction,
    )
    profile["starting_level"] = extraction.starting_level
    profile["notes"] = extraction.notes

    reply = await ask_conversational(
        "assess",
        language=state["language"],
        instruction=WRAP_INSTRUCTION,
        transcript=state["transcript"],
    )
    return {
        "stage": "confirm_profile",
        "stage_step": 0,
        "profile": profile,
        "history": history[-12:],
        "reply_text": reply,
        "ui": {"type": "idle"},
    }
