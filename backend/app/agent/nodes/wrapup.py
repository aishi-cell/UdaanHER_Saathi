"""Wrapup node, plan v2: end the way a good lesson does -- here is what you
did, here is what comes next.

Marks the skill completed when every must-land concept on her path landed
strong (else leaves it in progress for next time), shows the progress screen
while narrating it simply, then hands to close."""

from app.agent import milestones
from app.agent.llm_utils import ask_conversational
from app.agent.state import AgentState
from app.agent.teaching_utils import load_package, path_concept_ids, persistable_learner_id
from app.models import db

NARRATE_INSTRUCTION = (
    "The session is ending; her progress is on screen. Sum up today in the "
    "kindest honest way: {strong_count} idea(s) are solid, {shaky_count} "
    "you two will look at again together next time. Never grades or marks "
    "-- just 'this is solid' and 'this we'll see again'. {milestone_line}End "
    "by saying you'll say a proper goodbye next."
)
# Career roadmap (roadmap item 3): a session end is a natural moment to name
# what's next on her bigger journey, not just today's concepts.
MILESTONE_LINE_NEXT = (
    "On her bigger journey with this skill, the next milestone ahead of her "
    "is: {milestone}. Mention that warmly, in one short phrase. "
)
MILESTONE_LINE_ALL_DONE = (
    "On her bigger journey with this skill, she has already reached every "
    "milestone there is -- celebrate that warmly in one short phrase. "
)


async def run(state: AgentState) -> dict:
    package = load_package(state)
    grades = state["viva"]["grades"]
    strong_count = sum(1 for g in grades.values() if g == "strong")
    shaky_count = sum(1 for g in grades.values() if g == "shaky")

    ui: dict = {"type": "idle"}
    learner_id = persistable_learner_id(state)
    milestone_line = ""
    if learner_id and package is not None:
        must_land = {c.concept_id for c in package.curriculum.concepts if c.must_land}
        path_must = must_land & set(path_concept_ids(state, package))
        completed = bool(path_must) and all(grades.get(c) == "strong" for c in path_must)
        db.upsert_lesson_progress(
            learner_id, package.skill_id, "completed" if completed else "in_progress"
        )
        if completed:
            # Career roadmap (roadmap item 3): "completed a skill".
            db.mark_milestone(learner_id, package.skill_id, "completed_skill")
        ui = {"type": "show_progress", "payload": db.get_progress(learner_id)}

        achieved = {m.milestone_id for m in db.get_milestones(learner_id, package.skill_id)}
        next_m = milestones.next_milestone(achieved)
        milestone_line = (
            MILESTONE_LINE_NEXT.format(milestone=next_m.label_en)
            if next_m
            else MILESTONE_LINE_ALL_DONE
        )

    reply = await ask_conversational(
        "wrapup",
        language=state["language"],
        instruction=NARRATE_INSTRUCTION.format(
            strong_count=strong_count, shaky_count=shaky_count, milestone_line=milestone_line
        ),
        transcript=state["transcript"],
    )
    return {"stage": "close", "stage_step": 0, "reply_text": reply, "ui": ui}
