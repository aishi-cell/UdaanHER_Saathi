"""Teach node, plan v2: walk her personalized path one spoken micro-step at
a time, from the content store -- any skill, never a hardcoded curriculum.

Each turn narrates the current step from its teaching_notes (voice is the
interface; the show_lesson_step command is an optional visual aid). She can
interrupt with a question (answered, step held), continue (advance), or stop
(wrap up). Reaching the end of the path lands in viva.
"""

from typing import Literal

from pydantic import BaseModel

from app.agent.guards import teach_requires_profile
from app.agent.llm_utils import FRESH_TOPIC, ask_conversational, extract_structured, is_unclear
from app.agent.state import AgentState
from app.agent.teaching_utils import load_package, path_concept_ids, persistable_learner_id
from app.content import store
from app.models import db

NARRATE_INSTRUCTION = (
    "You are teaching her {interest}, one small spoken step at a time. "
    "This step ({position} of {total}) is about: {concept_label}.\n\n"
    "Teach exactly this, warmly, as if sitting beside her:\n{teaching_notes}\n\n"
    "{extra}End by asking softly if she is ready for the next bit or has a question."
)
ANSWER_INSTRUCTION = (
    "She just asked a question while you were teaching this step about "
    "{concept_label}. Answer HER question simply and warmly, staying true to "
    "these teaching notes (do not invent technique beyond them):\n"
    "{teaching_notes}\n\nThen gently ask if she wants to go on."
)
# Learning roadmap (roadmap item 4): a short preview of today's plan before
# diving into the first step, and an answer she can ask for again anytime.
PROGRESS_QUERY_INSTRUCTION = (
    "She just asked what she's already learned, or what's coming up next -- "
    "not a question about the lesson content itself. Answer warmly and "
    "briefly, in ONE short sentence, from this: already done today: {done}. "
    "Right now: {current}. Coming up after this: {next_up}. Then gently ask "
    "if she's ready to continue with {current}."
)
FINISH_INSTRUCTION = (
    "She has just finished the last step of today's path on {interest}. "
    "Warmly say the two of you will now chat a little about what you did "
    "together -- never call it a test or checking."
)
STOP_INSTRUCTION = (
    "She wants to stop for now. Reassure her warmly that stopping is fine "
    "and everything is remembered, and that you'll look at what she did "
    "today together before saying goodbye."
)


class TeachIntent(BaseModel):
    intent: Literal["question", "continue", "stop", "progress_query"]


def _ordered_concept_ids(steps: list[store.MicroStep]) -> list[str]:
    """Her path's concepts, in order, each once -- a step list can repeat a
    concept across several micro-steps (e.g. two c-grain steps)."""
    seen: set[str] = set()
    ids: list[str] = []
    for step in steps:
        if step.concept_id not in seen:
            seen.add(step.concept_id)
            ids.append(step.concept_id)
    return ids


def _concept_label(package: store.SkillPackage, concept_id: str) -> str:
    concept = package.concept(concept_id)
    # English label fed into the instruction, same as elsewhere in this
    # node -- the LLM narrates it in her language as part of a natural reply.
    return store.pick_language(concept.label, "en-IN") if concept else concept_id


def _step_ui(package: store.SkillPackage, steps: list[store.MicroStep], index: int, language: str) -> dict:
    step = steps[index]
    # A real tutorial clip beats a caption-only card (plan v2: video first,
    # diagram fallback) -- offer the store's clip when the step has no image.
    if not step.image:
        aids = package.aids_for_concept(step.concept_id, language)
        video = next((a for a in aids if a.kind == "video"), None)
        if video:
            return {
                "type": "show_video",
                "url": video.url_or_path,
                "caption": store.pick_language(step.caption, language),
            }
    return {
        "type": "show_lesson_step",
        "lesson_id": package.skill_id,
        "step_index": index,
        "total_steps": len(steps),
        "image": step.image,
        "caption": store.pick_language(step.caption, language),
    }


async def _narrate(
    state: AgentState,
    package: store.SkillPackage,
    steps: list[store.MicroStep],
    index: int,
    *,
    first: bool,
) -> dict:
    step = steps[index]
    label = _concept_label(package, step.concept_id)
    if first:
        # Learning roadmap (roadmap item 4): name the plan before starting,
        # e.g. "Hum pehle yeh seekhenge, phir yeh..." -- so she knows what
        # to expect instead of lessons just appearing one after another.
        concept_ids = _ordered_concept_ids(steps)
        upcoming = [_concept_label(package, c) for c in concept_ids[1:4]]
        more_after = len(concept_ids) > 4
        if upcoming:
            plan = ", then ".join(upcoming) + (", and a few more things" if more_after else "")
            extra = (
                f"Before teaching the first step, briefly name today's plan in one short "
                f"line -- you'll start with {label}, then {plan}. Then say you two will go "
                "slowly, one small thing at a time. "
            )
        else:
            extra = (
                "This is the start of today's path -- say you two will go slowly, "
                "one small thing at a time. "
            )
    else:
        extra = ""
    if not first and index > 0 and index % 3 == 0:
        # Every few steps, a human pause: is she tired, does she want to go
        # on or rest today? (User report: sessions ran on without a break.)
        extra += (
            "You two have done a few steps together now -- before teaching this "
            "one, warmly ask if she is comfortable going on or would rather "
            "rest and continue another day; stopping is completely fine and "
            "everything is remembered. "
        )
    reply = await ask_conversational(
        "teach",
        language=state["language"],
        instruction=NARRATE_INSTRUCTION.format(
            interest=(state.get("profile") or {}).get("interest", "this skill"),
            position=index + 1,
            total=len(steps),
            concept_label=label,
            teaching_notes=step.teaching_notes,
            extra=extra,
        ),
        # FRESH_TOPIC, not "" -- this is a new narration, not a re-ask; see
        # app.agent.llm_utils.FRESH_TOPIC.
        transcript=FRESH_TOPIC if first else state["transcript"],
    )
    return {
        "stage": "teach",
        "stage_step": 1,
        "step_index": index,
        "reply_text": reply,
        "ui": _step_ui(package, steps, index, state["language"]),
    }


async def run(state: AgentState) -> dict:
    if not teach_requires_profile(state):
        return {
            "stage": "confirm_profile",
            "stage_step": 0,
            "reply_text": "Pehle mujhe thoda aur jaanna hoga aapke baare mein.",
            "ui": {"type": "idle"},
        }

    package = load_package(state)
    if package is None or not package.curriculum.steps:
        # No teachable content for this skill (should be gated by discover;
        # defensive so a live demo degrades to a warm wrap, not a crash).
        return {
            "stage": "wrapup",
            "stage_step": 0,
            "reply_text": "Aaj ke liye itna hi taiyaar hai; chaliye dekhte hain aage kya hoga.",
            "ui": {"type": "idle"},
        }

    steps = package.steps_for_concepts(path_concept_ids(state, package))
    if not steps:
        steps = package.curriculum.steps

    # Entry from assess/confirm/resume: mark the skill in progress, teach step 0.
    if state["stage_step"] == 0:
        learner_id = persistable_learner_id(state)
        if learner_id:
            db.upsert_lesson_progress(learner_id, package.skill_id, "in_progress")
        return await _narrate(state, package, steps, 0, first=True)

    index = min(state.get("step_index") or 0, len(steps) - 1)
    current = steps[index]
    label = _concept_label(package, current.concept_id)

    if is_unclear(state["transcript"]):
        # With hands-free listening, an empty transcript is often noise or
        # her walking away -- advancing on it silently taught to an empty
        # room (user report). Hold the step and check in instead.
        reply = await ask_conversational(
            "teach",
            language=state["language"],
            instruction=(
                "You couldn't hear her clearly. Warmly check she is still "
                "there and ask if she wants you to continue with this step, "
                "say it again, or rest -- her pace, her choice."
            ),
            transcript="",
        )
        return {
            "stage": "teach",
            "stage_step": 1,
            "step_index": index,
            "reply_text": reply,
            "ui": _step_ui(package, steps, index, state["language"]),
        }
    else:
        intent = await extract_structured(
            "teach",
            language=state["language"],
            instruction=(
                "She is mid-lesson. Decide from her reply whether she is asking "
                "a question about what's being taught ('question'), ready to "
                "move on -- including short agreement like haan/accha/ok "
                "('continue'), wants to stop for today ('stop'), or is asking "
                "about her overall progress rather than this step's content -- "
                "e.g. 'ab tak maine kya seekha?', 'ab aage kya hai?', 'what have "
                "I learned so far', 'what's next' ('progress_query'). Her "
                "speech-to-text transcript may be imperfect, informal, or "
                "code-mixed -- best reasonable guess."
            ),
            transcript=state["transcript"],
            schema=TeachIntent,
        )

    if intent.intent == "progress_query":
        # Learning roadmap (roadmap item 4): she can ask this at any point,
        # not just hear it once at the start -- answered from the same
        # concept order the plan preview used, then the step is held.
        concept_ids = _ordered_concept_ids(steps)
        position = concept_ids.index(current.concept_id) if current.concept_id in concept_ids else 0
        done = [_concept_label(package, c) for c in concept_ids[:position]]
        next_up = [_concept_label(package, c) for c in concept_ids[position + 1 : position + 3]]
        reply = await ask_conversational(
            "teach",
            language=state["language"],
            instruction=PROGRESS_QUERY_INSTRUCTION.format(
                done=", ".join(done) if done else "nothing yet -- you're just getting started today",
                current=label,
                next_up=", ".join(next_up) if next_up else "nothing -- this is the last thing for today",
            ),
            transcript=state["transcript"],
        )
        return {
            "stage": "teach",
            "stage_step": 1,
            "step_index": index,
            "reply_text": reply,
            "ui": _step_ui(package, steps, index, state["language"]),
        }

    if intent.intent == "question":
        reply = await ask_conversational(
            "teach",
            language=state["language"],
            instruction=ANSWER_INSTRUCTION.format(
                concept_label=label, teaching_notes=current.teaching_notes
            ),
            transcript=state["transcript"],
        )
        return {
            "stage": "teach",
            "stage_step": 1,
            "step_index": index,
            "reply_text": reply,
            "ui": _step_ui(package, steps, index, state["language"]),
        }

    if intent.intent == "stop":
        reply = await ask_conversational(
            "teach",
            language=state["language"],
            instruction=STOP_INSTRUCTION,
            transcript=state["transcript"],
        )
        return {
            "stage": "wrapup",
            "stage_step": 0,
            "reply_text": reply,
            "ui": {"type": "idle"},
        }

    # continue
    if index + 1 < len(steps):
        return await _narrate(state, package, steps, index + 1, first=False)

    reply = await ask_conversational(
        "teach",
        language=state["language"],
        instruction=FINISH_INSTRUCTION.format(
            interest=(state.get("profile") or {}).get("interest", "this skill")
        ),
        transcript=state["transcript"],
    )
    return {
        "stage": "viva",
        "stage_step": 0,
        "reply_text": reply,
        "ui": {"type": "idle"},
    }
