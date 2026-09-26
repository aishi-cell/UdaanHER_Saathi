"""Real resume node (T22): welcome a returning learner back by name and
pick up at her next gap.

Reached two ways:
- POST /api/session with a resolved name+PIN (typed path) starts the graph
  at stage="resume", so this node's reply becomes the session greeting.
- greet's voice path (name + spoken PIN) chains straight into run() below
  in the same turn, so the welcome she hears is already in her language
  and never costs a throwaway round-trip (roadmap item 2).

Her remaining path is rebuilt from persisted concept_mastery: every
curriculum concept not yet 'strong', in curriculum order -- so a woman who
mastered half the skill last visit never re-sits the half she finished.

Career roadmap (roadmap item 3): most milestones are auto-tracked, but two
happen in her real life, off-platform -- a real customer, a real sale --
and there's no way to observe those from inside a conversation. This node
is the one place she's asked about them, and only when it's actually
relevant: a returning learner whose next pending milestone for this skill
is one of those two (i.e. she's already made a product and learned to
price it last time). Everyone else's welcome is unchanged, one turn, same
as before this existed.
"""

from typing import Literal

from pydantic import BaseModel

from app.agent import milestones
from app.agent.llm_utils import FRESH_TOPIC, ask_conversational, extract_structured, is_unclear
from app.agent.state import AgentState, ProfileDraft
from app.agent.teaching_utils import load_package
from app.content import store
from app.models import db

WELCOME_BACK_INSTRUCTION = (
    "She is BACK -- you have met before. Her name is {name} and she is "
    "learning {interest}. Welcome her back warmly by name, clearly glad to "
    "see her again. {progress_line} {milestone_line}Say you two will pick "
    "up right where she left off."
)
PROGRESS_LINE_SOME_DONE = (
    "Last time she worked through some of it already -- {remaining} small "
    "steps remain, so acknowledge how far she has come."
)
PROGRESS_LINE_FRESH = "This visit continues the path you planned together."
# Career roadmap (roadmap item 3): "explain her current progress and the
# next milestone" -- the most natural moment for this is right when she
# returns, before diving back into the lesson content. Only used when the
# next milestone is auto-tracked -- the two self-reported ones get the
# active check-in below instead, never both (that would be redundant).
MILESTONE_LINE_NEXT = (
    "On her bigger journey with this skill, the next milestone ahead of her "
    "is: {milestone}. Mention that warmly, in one short phrase, as "
    "something to look forward to. "
)
MILESTONE_LINE_ALL_DONE = (
    "On her bigger journey with this skill, she has already reached every "
    "milestone there is -- celebrate that warmly in one short phrase. "
)
# Self-reported milestones: a real event in her life since her last visit,
# not something the app can observe. Warm, low-pressure, easy to skip.
ASK_FOUND_CUSTOMER_INSTRUCTION = (
    "Before picking up where she left off, gently check in on one thing: "
    "has she found her first customer for {interest} yet, since you two "
    "last spoke? Make clear there's no rush at all -- she can simply say "
    "yes or not yet, either is completely fine."
)
ASK_FIRST_PAID_ORDER_INSTRUCTION = (
    "Before picking up where she left off, gently check in on one thing: "
    "has she completed her first paid order for {interest} yet, since you "
    "two last spoke? Make clear there's no rush at all -- she can simply "
    "say yes or not yet, either is completely fine."
)
REASK_MILESTONE_CHECK_INSTRUCTION = (
    "You couldn't quite make out her answer. Warmly and briefly ask again, "
    "simply: {question} -- a plain yes or not-yet is all you need."
)
MILESTONE_ACHIEVED_ACK_INSTRUCTION = (
    "Wonderful -- she just told you she has {milestone}! Celebrate this "
    "warmly and genuinely, this is a real achievement. Then say you two "
    "will pick up right where she left off."
)
MILESTONE_NOT_YET_ACK_INSTRUCTION = (
    "Not yet -- completely fine, no pressure at all, it comes in its own "
    "time. Reassure her warmly, then say you two will pick up right where "
    "she left off."
)


class MilestoneCheckExtraction(BaseModel):
    achieved: Literal["yes", "not_yet", "unclear"]


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


def _skill_id_for(state: AgentState) -> str | None:
    return state.get("skill_id") or (state.get("profile") or {}).get("interest") or None


def _achieved_milestones(state: AgentState) -> set[str]:
    learner_id = state.get("learner_id")
    skill_id = _skill_id_for(state)
    if not learner_id or not skill_id:
        return set()
    return {m.milestone_id for m in db.get_milestones(learner_id, skill_id)}


def milestone_line_for(state: AgentState) -> str:
    """The passive "next milestone ahead of her" mention -- only for an
    auto-tracked next milestone; the two self-reported ones are asked about
    actively instead (_reportable_milestone), never mentioned passively
    too, which would be redundant in the same breath."""
    if not state.get("learner_id") or not _skill_id_for(state):
        return ""
    next_m = milestones.next_milestone(_achieved_milestones(state))
    if next_m is None:
        return MILESTONE_LINE_ALL_DONE
    if not next_m.auto_tracked:
        return ""
    return MILESTONE_LINE_NEXT.format(milestone=next_m.label_en)


def _reportable_milestone(state: AgentState) -> milestones.Milestone | None:
    """Her next milestone, but only if it's one she'd need to tell Saathi
    about herself (a real customer, a real sale) -- the auto-tracked ones
    never reach here, nothing to ask about them."""
    if not state.get("learner_id") or not _skill_id_for(state):
        return None
    next_m = milestones.next_milestone(_achieved_milestones(state))
    if next_m is not None and not next_m.auto_tracked:
        return next_m
    return None


async def _ask_milestone_check(state: AgentState, reportable: milestones.Milestone) -> dict:
    interest = (state.get("profile") or {}).get("interest", "this skill")
    instruction = (
        ASK_FOUND_CUSTOMER_INSTRUCTION
        if reportable.id == "found_customer"
        else ASK_FIRST_PAID_ORDER_INSTRUCTION
    ).format(interest=interest)
    reply = await ask_conversational(
        "resume", language=state["language"], instruction=instruction, transcript=FRESH_TOPIC
    )
    return {"stage": "resume", "stage_step": 1, "reply_text": reply, "ui": {"type": "idle"}}


def _check_question_text(reportable: milestones.Milestone, interest: str) -> str:
    if reportable.id == "found_customer":
        return f"has she found her first customer for {interest} yet"
    return f"has she completed her first paid order for {interest} yet"


async def _handle_milestone_check_answer(state: AgentState) -> dict:
    reportable = _reportable_milestone(state)
    if reportable is None:
        # Very unlikely (e.g. marked by another session in between), but
        # degrade gracefully -- just move on to teaching, no dead end.
        reply = await ask_conversational(
            "resume",
            language=state["language"],
            instruction="Warmly say you two will pick up right where she left off.",
            transcript=FRESH_TOPIC,
        )
        return {**build_resume_updates(state), "reply_text": reply}

    interest = (state.get("profile") or {}).get("interest", "this skill")
    if is_unclear(state["transcript"]):
        reply = await ask_conversational(
            "resume",
            language=state["language"],
            instruction=REASK_MILESTONE_CHECK_INSTRUCTION.format(
                question=_check_question_text(reportable, interest)
            ),
            transcript="",
        )
        return {"stage": "resume", "stage_step": 1, "reply_text": reply, "ui": {"type": "idle"}}

    extraction = await extract_structured(
        "resume",
        language=state["language"],
        instruction=(
            "She was just asked, warmly and with no pressure, whether she's "
            "reached a milestone yet (found a customer / made a sale). "
            "Work out her answer: 'yes' if she clearly says she has, "
            "'not_yet' if she says no or not yet (completely fine either "
            "way), or 'unclear' if you genuinely can't tell. Her transcript "
            "may be informal, incomplete, or code-mixed -- best reasonable "
            "guess, but use 'unclear' rather than assuming."
        ),
        transcript=state["transcript"],
        schema=MilestoneCheckExtraction,
    )

    if extraction.achieved == "unclear":
        reply = await ask_conversational(
            "resume",
            language=state["language"],
            instruction=REASK_MILESTONE_CHECK_INSTRUCTION.format(
                question=_check_question_text(reportable, interest)
            ),
            transcript="",
        )
        return {"stage": "resume", "stage_step": 1, "reply_text": reply, "ui": {"type": "idle"}}

    achieved = extraction.achieved == "yes"
    learner_id = state.get("learner_id")
    skill_id = _skill_id_for(state)
    if achieved and learner_id and skill_id:
        db.mark_milestone(learner_id, skill_id, reportable.id)

    reply = await ask_conversational(
        "resume",
        language=state["language"],
        instruction=(
            MILESTONE_ACHIEVED_ACK_INSTRUCTION.format(milestone=reportable.label_en)
            if achieved
            else MILESTONE_NOT_YET_ACK_INSTRUCTION
        ),
        transcript=state["transcript"],
    )
    return {**build_resume_updates(state), "reply_text": reply}


async def run(state: AgentState) -> dict:
    if state.get("stage_step", 0) == 1:
        return await _handle_milestone_check_answer(state)

    profile = state.get("profile") or {}
    reportable = _reportable_milestone(state)
    if reportable is not None:
        return await _ask_milestone_check(state, reportable)

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
            milestone_line=milestone_line_for(state),
        ),
        transcript=FRESH_TOPIC,
    )
    return {**updates, "reply_text": reply}
