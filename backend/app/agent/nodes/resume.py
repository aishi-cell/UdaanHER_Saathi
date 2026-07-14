"""Real resume node (T22): welcome a returning learner back by name and
pick up at her next gap.

Reached two ways:
- POST /api/session with a resolved name+PIN (typed path) starts the graph
  at stage="resume", so this node's reply becomes the session greeting.
- greet's voice path (name + spoken PIN) reuses this module's helpers to do
  the same hand-off inside the conversation.

Her remaining path is rebuilt from persisted concept_mastery: every
curriculum concept not yet 'strong', in curriculum order -- so a woman who
mastered half the skill last visit never re-sits the half she finished.
"""

from app.agent.llm_utils import ask_conversational
from app.agent.state import AgentState, ProfileDraft
from app.agent.teaching_utils import load_package
from app.content import store
from app.models import db

WELCOME_BACK_INSTRUCTION = (
    "She is BACK -- you have met before. Her name is {name} and she is "
    "learning {interest}. Welcome her back warmly by name, clearly glad to "
    "see her again. {progress_line} Say you two will pick up right where "
    "she left off."
)
PROGRESS_LINE_SOME_DONE = (
    "Last time she worked through some of it already -- {remaining} small "
    "steps remain, so acknowledge how far she has come."
)
PROGRESS_LINE_FRESH = "This visit continues the path you planned together."


def profile_from_learner(learner) -> ProfileDraft:
    return ProfileDraft(
        name=learner.name,
        village=learner.village or "",
        interest=learner.interest_skill or "",
        starting_level=learner.starting_level or "some",
        notes=learner.notes or "",
    )


def resume_learning_path(package: store.SkillPackage, mastery: dict[str, str]) -> list[str]:
    """Concepts not yet 'strong', in curriculum order; if she finished
    everything, a short must-land refresh instead of an empty session."""
    path = [
        c.concept_id
        for c in package.curriculum.concepts
        if mastery.get(c.concept_id) != "strong"
    ]
    if not path:
        path = [c.concept_id for c in package.curriculum.concepts if c.must_land]
    return path


def build_resume_updates(state: AgentState) -> dict:
    """The state hand-off shared by this node and greet's voice PIN path:
    learning path from persisted mastery, next stop teach."""
    learner_id = state.get("learner_id")
    mastery = db.get_mastery_map(learner_id) if learner_id else {}
    package = load_package(state)
    path = resume_learning_path(package, mastery) if package else []
    return {
        "stage": "teach",
        "stage_step": 0,
        "learning_path": path,
        "concept_estimates": {},
        "ui": {"type": "idle"},
    }


async def run(state: AgentState) -> dict:
    profile = state.get("profile") or {}
    updates = build_resume_updates(state)
    remaining = len(updates["learning_path"])
    mastered_any = bool(
        state.get("learner_id") and db.get_mastery_map(state["learner_id"])
    )
    progress_line = (
        PROGRESS_LINE_SOME_DONE.format(remaining=remaining)
        if mastered_any and remaining
        else PROGRESS_LINE_FRESH
    )
    reply = await ask_conversational(
        "resume",
        language=state["language"],
        instruction=WELCOME_BACK_INSTRUCTION.format(
            name=profile.get("name", ""),
            interest=profile.get("interest", "her skill"),
            progress_line=progress_line,
        ),
        transcript="",
    )
    return {**updates, "reply_text": reply}
