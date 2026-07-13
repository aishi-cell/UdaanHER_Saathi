"""Assess node, plan v2: the diagnostic that makes personalization real.

3-4 story-questions about her chosen skill, aimed at the skill's concepts
(from the content store), then ONE structured extraction producing both the
profile level AND a per-concept estimate ("knows" | "gap"). The learning
path is then computed in code -- gap concepts only, in curriculum order --
so a woman who already sews never sits through "this is a needle".
"""

from typing import Literal

from pydantic import BaseModel, Field

from app.agent.llm_utils import ask_conversational, extract_structured, is_unclear
from app.agent.state import AgentState
from app.content import store

MAX_QUESTIONS = 3

QUESTION_INSTRUCTION = (
    "Here is what you already know about her: name {name}, from {village}, "
    "wants to learn {interest}. Do not ask about any of that again -- it's "
    "already been covered.\n\n"
    "You are quietly finding out which of these ideas she already knows, "
    "through stories -- NEVER by quizzing: {concept_labels}.\n\n"
    "Ask her a warm, story-style question about her experience with {interest} "
    "-- something like 'Have you ever tried...' or 'Tell me about a time "
    "you...'. Aim it so her answer will reveal something about the ideas "
    "above that the conversation so far hasn't covered yet. This is question "
    "{question_number} of {max_questions}; don't repeat a question already "
    "asked.\n\n"
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


class ConceptEstimate(BaseModel):
    concept_id: str
    estimate: Literal["knows", "gap"] = Field(
        description=(
            "'knows' ONLY if her answers gave real evidence she already has "
            "this idea; when unsure, 'gap' -- teaching something she knows "
            "costs minutes, skipping something she needs costs the skill"
        )
    )


class DiagnosticExtraction(BaseModel):
    starting_level: Literal["new", "some", "experienced"]
    notes: str
    concept_estimates: list[ConceptEstimate]


def _load_package(state: AgentState) -> store.SkillPackage | None:
    skill_id = state.get("skill_id")
    if not skill_id or not store.has_skill(skill_id):
        return None
    return store.load_skill(skill_id)


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


def _learning_path(package: store.SkillPackage, estimates: dict[str, str]) -> list[str]:
    """Gap concepts in curriculum order; if she truly knows everything, a
    short must-land refresh instead of an empty session."""
    path = [
        c.concept_id
        for c in package.curriculum.concepts
        if estimates.get(c.concept_id) != "knows"
    ]
    if not path:
        path = [c.concept_id for c in package.curriculum.concepts if c.must_land]
    return path


async def run(state: AgentState) -> dict:
    profile = dict(state.get("profile") or {})
    interest = profile.get("interest", "this skill")
    step = state["stage_step"]
    package = _load_package(state)
    concept_labels = (
        "; ".join(
            f"{c.concept_id}: {store.pick_language(c.label, 'en-IN')}"
            for c in package.curriculum.concepts
        )
        if package
        else "(general experience with the skill)"
    )

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
                concept_labels=concept_labels,
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
            f"Based on the whole conversation so far, judge (a) her starting "
            f"level with {interest} as 'new' (never tried), 'some' (has tried "
            f"a bit), or 'experienced' (comfortable already); (b) for EACH of "
            f"these concept ids, whether her answers show she already knows "
            f"it: {concept_labels}. Also write one short note in English "
            f"summarising what she already seems to know, for another mentor "
            f"to read later.\n\nConversation so far:\n{conversation_so_far}"
        ),
        transcript=state["transcript"],
        schema=DiagnosticExtraction,
    )
    profile["starting_level"] = extraction.starting_level
    profile["notes"] = extraction.notes

    estimates = {e.concept_id: e.estimate for e in extraction.concept_estimates}
    learning_path = _learning_path(package, estimates) if package else []

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
        "concept_estimates": estimates,
        "learning_path": learning_path,
        "history": history[-12:],
        "reply_text": reply,
        "ui": {"type": "idle"},
    }
