"""Reteach node, plan v2: where she is shaky, explain DIFFERENTLY -- a new
analogy, a vetted video from the store, or a live-generated SVG diagram --
then gently re-check with one fresh question.

Code-enforced limits (Spec S9.1 spirit): aids come only from the store index
or the sanitized SVG generator; max 2 reteach rounds per concept, then the
concept is marked revisit-next-session and the mentor moves on warmly --
never a third drill.
"""

from app.agent.guards import can_start_reteach
from app.agent.llm_utils import ask_conversational, extract_structured, is_unclear
from app.agent.nodes.viva import VivaGrade, _find_question
from app.agent.state import AgentState
from app.agent.teaching_utils import (
    coverage_order,
    load_package,
    path_concept_ids,
    persistable_learner_id,
)
from app.content import store, visuals
from app.models import db

EXPLAIN_INSTRUCTION = (
    "Earlier, this idea did not quite land for her: {concept_label}. "
    "Explain it AGAIN but DIFFERENTLY -- a fresh everyday analogy from "
    "village life, not the same words as before. Ground yourself in these "
    "teaching notes (do not invent technique beyond them):\n{teaching_notes}\n\n"
    "{aid_line}"
    "Then gently work this into the chat as a question for her: {question}"
)
EARN_TRANSITION_INSTRUCTION = (
    "{lead}Say that next you two will talk about the best part -- how to "
    "EARN from this skill."
)
LEAD_LANDED = "It clicked for her this time -- celebrate that warmly in one sentence. "
LEAD_CAPPED = (
    "One idea hasn't fully landed today, and that is completely fine -- say "
    "warmly (never any blame) that you two will look at it again next time, "
    "it is safely remembered. "
)
GRADE_INSTRUCTION = (
    "Grade her spoken answer to this question about {concept_label}.\n"
    "Question: {question}\n"
    "Answers like these mean she has the idea (grade 'strong'):\n{sounds_right}\n"
    "Answers like these mean she is confused (grade 'shaky'):\n{sounds_confused}\n"
    "Her transcript may be informal, incomplete, code-mixed, or imperfectly "
    "transcribed -- judge the UNDERSTANDING underneath the words."
)
REASK_INSTRUCTION = (
    "You couldn't quite make out her answer. Warmly say you didn't catch "
    "that, and ask the same thing again in simpler words: {question}"
)


def _eligible_shaky(state: AgentState, package: store.SkillPackage) -> list[str]:
    coverage = coverage_order(package, path_concept_ids(state, package))
    grades = state["viva"]["grades"]
    counts = state.get("reteach_counts") or {}
    return [
        c for c in coverage if grades.get(c) == "shaky" and can_start_reteach(c, counts)
    ]


async def _aid_ui(
    state: AgentState, package: store.SkillPackage, concept_id: str, teaching_notes: str
) -> tuple[dict, str]:
    """(ui command, one-line instruction telling the LLM what's on screen).
    Store aids first (language-ranked); live SVG diagram as fallback; plain
    voice if generation fails -- visuals are optional, speech must stand alone."""
    concept = package.concept(concept_id)
    label = store.pick_language(concept.label, state["language"]) if concept else concept_id

    aids = package.aids_for_concept(concept_id, state["language"])
    if aids:
        aid = aids[0]
        if aid.kind == "video":
            return (
                {"type": "show_video", "url": aid.url_or_path, "caption": label},
                "A short helpful video is playing on her screen -- mention it. ",
            )
        return (
            {
                "type": "show_lesson_step",
                "lesson_id": package.skill_id,
                "step_index": 0,
                "total_steps": 1,
                "image": aid.url_or_path,
                "caption": label,
            },
            "A simple diagram is on her screen -- point to it while explaining. ",
        )

    diagram = await visuals.generate_diagram(
        store.pick_language(concept.label, "en-IN") if concept else concept_id,
        teaching_notes,
        language=state["language"],
    )
    if diagram:
        return (
            {
                "type": "show_lesson_step",
                "lesson_id": package.skill_id,
                "step_index": 0,
                "total_steps": 1,
                "image": diagram,
                "caption": label,
            },
            "A simple diagram is on her screen -- point to it while explaining. ",
        )
    return {"type": "idle"}, ""


async def _explain_and_recheck(state: AgentState, package: store.SkillPackage, concept_id: str) -> dict:
    concept = package.concept(concept_id)
    label = store.pick_language(concept.label, "en-IN") if concept else concept_id
    notes = " ".join(s.teaching_notes for s in package.steps_for_concepts([concept_id])) or label

    asked = list(state["viva"]["question_ids_asked"])
    questions = package.questions_for_concept(concept_id)
    fresh = [q for q in questions if q.question_id not in asked]
    # Prefer a question she hasn't heard; if the rubric is exhausted, reuse
    # the first one (reworded by the LLM in conversation).
    question = fresh[0] if fresh else questions[0]

    ui, aid_line = await _aid_ui(state, package, concept_id, notes)

    reply = await ask_conversational(
        "reteach",
        language=state["language"],
        instruction=EXPLAIN_INSTRUCTION.format(
            concept_label=label,
            teaching_notes=notes,
            aid_line=aid_line,
            question=question.question,
        ),
        transcript=state["transcript"],
    )
    counts = dict(state.get("reteach_counts") or {})
    counts[concept_id] = counts.get(concept_id, 0) + 1
    return {
        "stage": "reteach",
        "stage_step": 1,
        "reteach_counts": counts,
        "viva": {
            "question_ids_asked": asked + [question.question_id],
            "grades": dict(state["viva"]["grades"]),
        },
        "reply_text": reply,
        "ui": ui,
    }


async def _next_or_earn(state: AgentState, package: store.SkillPackage, *, lead: str = "") -> dict:
    eligible = _eligible_shaky(state, package)
    if eligible:
        return await _explain_and_recheck(state, package, eligible[0])
    reply = await ask_conversational(
        "reteach",
        language=state["language"],
        instruction=EARN_TRANSITION_INSTRUCTION.format(lead=lead),
        transcript=state["transcript"],
    )
    return {"stage": "earn", "stage_step": 0, "reply_text": reply, "ui": {"type": "idle"}}


async def run(state: AgentState) -> dict:
    package = load_package(state)
    if package is None:
        return {
            "stage": "wrapup",
            "stage_step": 0,
            "reply_text": "Chaliye dekhte hain aaj humne kya kya kiya.",
            "ui": {"type": "idle"},
        }

    # Entry from viva: pick the first shaky concept and re-explain it.
    if state["stage_step"] == 0:
        return await _next_or_earn(state, package)

    # Her re-check answer just arrived; the current question is the last asked.
    asked = state["viva"]["question_ids_asked"]
    question = _find_question(package, asked[-1]) if asked else None
    if question is None:
        return await _next_or_earn(state, package)

    if is_unclear(state["transcript"]):
        reply = await ask_conversational(
            "reteach",
            language=state["language"],
            instruction=REASK_INSTRUCTION.format(question=question.question),
            transcript="",
        )
        return {"stage": "reteach", "stage_step": 1, "reply_text": reply, "ui": {"type": "idle"}}

    concept_id = question.concept_id
    concept = package.concept(concept_id)
    graded: VivaGrade = await extract_structured(
        "reteach",
        language=state["language"],
        instruction=GRADE_INSTRUCTION.format(
            concept_label=store.pick_language(concept.label, "en-IN") if concept else concept_id,
            question=question.question,
            sounds_right="\n".join(f"- {s}" for s in question.sounds_right),
            sounds_confused="\n".join(f"- {s}" for s in question.sounds_confused),
        ),
        transcript=state["transcript"],
        schema=VivaGrade,
    )

    grades = dict(state["viva"]["grades"])
    grades[concept_id] = graded.grade
    counts = dict(state.get("reteach_counts") or {})
    learner_id = persistable_learner_id(state)
    if learner_id:
        db.upsert_concept_mastery(
            learner_id, concept_id, graded.grade, reteach_count=counts.get(concept_id, 0)
        )

    updated = dict(state)
    updated["viva"] = {"question_ids_asked": list(asked), "grades": grades}
    updated["reteach_counts"] = counts

    if graded.grade == "strong":
        result = await _next_or_earn(updated, package, lead=LEAD_LANDED)
    elif not can_start_reteach(concept_id, counts):
        result = await _next_or_earn(updated, package, lead=LEAD_CAPPED)
    else:
        result = await _explain_and_recheck(updated, package, concept_id)  # one more round
    # Carry the grade update through whatever branch we took.
    merged_viva = result.get("viva") or updated["viva"]
    merged_viva["grades"] = {**grades, **merged_viva["grades"]}
    result["viva"] = merged_viva
    return result
