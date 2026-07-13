"""Viva node, plan v2: "let's chat about what we did" -- one rubric question
per path concept, graded strong/shaky against the store's spoken exemplars.

Framing is everything: grades are never spoken, questions come only from the
rubric file, and the reteach-vs-earn routing is computed in code from the
grades -- never by asking the LLM "should we reteach?".
"""

from typing import Literal

from pydantic import BaseModel

from app.agent.llm_utils import ask_conversational, extract_structured, is_unclear
from app.agent.state import AgentState
from app.agent.teaching_utils import (
    coverage_order,
    load_package,
    path_concept_ids,
    persistable_learner_id,
)
from app.content import store
from app.models import db

ASK_INSTRUCTION = (
    "You are chatting warmly about what you both just did -- NEVER as a "
    "test. {feedback_lead}Now, working the following question naturally "
    "into the chat, ask her: {question}"
)
REASK_INSTRUCTION = (
    "You couldn't quite make out her answer. Warmly say you didn't catch "
    "that, and ask the same thing again in simpler words: {question}"
)
GRADE_INSTRUCTION = (
    "Grade her spoken answer to this question about {concept_label}.\n"
    "Question: {question}\n"
    "Answers like these mean she has the idea (grade 'strong'):\n{sounds_right}\n"
    "Answers like these mean she is confused (grade 'shaky'):\n{sounds_confused}\n"
    "Her transcript may be informal, incomplete, code-mixed, or imperfectly "
    "transcribed -- judge the UNDERSTANDING underneath the words, the way a "
    "kind teacher listens, not the vocabulary or grammar."
)


class VivaGrade(BaseModel):
    grade: Literal["strong", "shaky"]
    one_line_reason: str


def _question_for_concept(
    package: store.SkillPackage, concept_id: str, asked: list[str]
) -> store.RubricQuestion | None:
    for q in package.questions_for_concept(concept_id):
        if q.question_id not in asked:
            return q
    return None


def _next_ungraded(coverage: list[str], grades: dict[str, str]) -> str | None:
    for concept_id in coverage:
        if concept_id not in grades:
            return concept_id
    return None


def _find_question(package: store.SkillPackage, question_id: str) -> store.RubricQuestion | None:
    for q in package.rubrics.questions:
        if q.question_id == question_id:
            return q
    return None


async def _ask(
    state: AgentState,
    package: store.SkillPackage,
    concept_id: str,
    viva: dict,
    *,
    feedback_lead: str,
) -> dict:
    question = _question_for_concept(package, concept_id, viva["question_ids_asked"])
    if question is None:  # rubric exhausted for this concept: treat as covered
        grades = dict(viva["grades"])
        grades.setdefault(concept_id, "strong")
        viva = {"question_ids_asked": viva["question_ids_asked"], "grades": grades}
        return await _advance(state, package, viva, feedback_lead=feedback_lead)

    reply = await ask_conversational(
        "viva",
        language=state["language"],
        instruction=ASK_INSTRUCTION.format(feedback_lead=feedback_lead, question=question.question),
        transcript=state["transcript"],
    )
    return {
        "stage": "viva",
        "stage_step": 1,
        "viva": {
            "question_ids_asked": viva["question_ids_asked"] + [question.question_id],
            "grades": viva["grades"],
        },
        "reply_text": reply,
        "ui": {"type": "idle"},
    }


async def _advance(
    state: AgentState, package: store.SkillPackage, viva: dict, *, feedback_lead: str
) -> dict:
    coverage = coverage_order(package, path_concept_ids(state, package))
    next_concept = _next_ungraded(coverage, viva["grades"])
    if next_concept is not None:
        return await _ask(state, package, next_concept, viva, feedback_lead=feedback_lead)

    # All path concepts graded: route in code, never by the LLM.
    shaky = [c for c in coverage if viva["grades"].get(c) == "shaky"]
    next_stage = "reteach" if shaky else "earn"
    instruction = (
        (
            feedback_lead
            + "Say warmly that there is one thing the two of you will look at "
            "again together, from a different side -- it is completely normal."
        )
        if shaky
        else (
            feedback_lead
            + "Tell her warmly she has understood today's work, and that next "
            "you two will talk about the best part -- how to EARN from this."
        )
    )
    reply = await ask_conversational(
        "viva", language=state["language"], instruction=instruction, transcript=state["transcript"]
    )
    return {
        "stage": next_stage,
        "stage_step": 0,
        "viva": viva,
        "reply_text": reply,
        "ui": {"type": "idle"},
    }


async def run(state: AgentState) -> dict:
    package = load_package(state)
    if package is None:
        return {
            "stage": "wrapup",
            "stage_step": 0,
            "reply_text": "Chaliye dekhte hain aaj humne kya kya kiya.",
            "ui": {"type": "idle"},
        }

    viva = {
        "question_ids_asked": list(state["viva"]["question_ids_asked"]),
        "grades": dict(state["viva"]["grades"]),
    }

    # Entry from teach: ask the first question.
    if state["stage_step"] == 0:
        return await _advance(state, package, viva, feedback_lead="")

    # An answer just arrived for the last asked question.
    last_id = viva["question_ids_asked"][-1] if viva["question_ids_asked"] else None
    question = _find_question(package, last_id) if last_id else None
    if question is None:
        return await _advance(state, package, viva, feedback_lead="")

    if is_unclear(state["transcript"]):
        reply = await ask_conversational(
            "viva",
            language=state["language"],
            instruction=REASK_INSTRUCTION.format(question=question.question),
            transcript="",
        )
        return {"stage": "viva", "stage_step": 1, "reply_text": reply, "ui": {"type": "idle"}}

    concept = package.concept(question.concept_id)
    graded: VivaGrade = await extract_structured(
        "viva",
        language=state["language"],
        instruction=GRADE_INSTRUCTION.format(
            concept_label=store.pick_language(concept.label, "en-IN") if concept else question.concept_id,
            question=question.question,
            sounds_right="\n".join(f"- {s}" for s in question.sounds_right),
            sounds_confused="\n".join(f"- {s}" for s in question.sounds_confused),
        ),
        transcript=state["transcript"],
        schema=VivaGrade,
    )
    viva["grades"][question.concept_id] = graded.grade

    learner_id = persistable_learner_id(state)
    if learner_id:
        db.upsert_concept_mastery(learner_id, question.concept_id, graded.grade)

    # Encouraging micro-feedback (the grade itself is never spoken), then on.
    feedback_lead = (
        "She just answered well -- give one short warm sentence of real "
        "appreciation for what she said. "
        if graded.grade == "strong"
        else "Her last answer wandered a little -- gently affirm the effort "
        "without any correction yet. "
    )
    return await _advance(state, package, viva, feedback_lead=feedback_lead)
