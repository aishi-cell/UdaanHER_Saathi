"""Practice node (user-requested): after viva/reteach, she does one small
real-world practice task and can photograph her work for warm review.

step 0  set ONE small hands-on task from today's concepts; the camera
        button appears (request_photo)
step 1  her response arrives as either
          - a photo: main.py has already run the vision model and hands us
            its observations as a transcript prefixed "[photo]" -- review
            against the teaching notes, one praise + one gentle adjustment
          - voice: "done / skip / can't right now" -- all fine, encourage
            and move on
        Either way the session flows on to earning.
"""

from app.agent.llm_utils import ask_conversational, is_unclear
from app.agent.state import AgentState
from app.agent.teaching_utils import load_package, path_concept_ids

PHOTO_MARKER = "[photo]"

SET_TASK_INSTRUCTION = (
    "Today she worked on these ideas about {interest}: {concept_labels}.\n"
    "Give her ONE small practice task she can do right now with things at "
    "home, tied to those ideas (e.g. practice lines on old paper; measure a "
    "family member twice). Then tell her: when done, she can tap the camera "
    "button and show you a photo of her work -- or just tell you about it. "
    "Make clear the photo is optional and this is practice, never judging."
)
REVIEW_INSTRUCTION = (
    "She photographed her practice work on {interest}. What the photo "
    "shows (from an assistant who examined it): {observations}\n\n"
    "The teaching notes she practiced from:\n{notes}\n\n"
    "Give her warm, specific feedback: FIRST one thing genuinely done well "
    "(be concrete, reference what is visible), then ONE gentle adjustment "
    "for next time -- never more than one, never the word 'wrong'. Close "
    "by saying you two will now talk about earning from this skill."
)
NO_PHOTO_INSTRUCTION = (
    "She responded about her practice by voice (or wants to skip the "
    "photo) -- completely fine. Encourage her warmly to keep practicing "
    "when she can, and say you two will now talk about earning from "
    "this skill."
)
REASK_INSTRUCTION = (
    "You couldn't quite hear her. Warmly say she can tap the camera to "
    "show her practice work, tell you about it, or you two can simply "
    "move on -- her choice."
)


def _concept_labels(state: AgentState) -> tuple[str, str]:
    package = load_package(state)
    if package is None:
        return "(today's skill work)", "(the steps taught today)"
    from app.content import store

    ids = set(path_concept_ids(state, package))
    labels = "; ".join(
        store.pick_language(c.label, "en-IN")
        for c in package.curriculum.concepts
        if c.concept_id in ids
    )
    notes = "\n".join(
        f"- {s.teaching_notes}" for s in package.curriculum.steps if s.concept_id in ids
    )
    return labels or "(today's skill work)", notes or "(the steps taught today)"


async def run(state: AgentState) -> dict:
    interest = (state.get("profile") or {}).get("interest", "this skill")
    labels, notes = _concept_labels(state)

    if state["stage_step"] == 0:
        reply = await ask_conversational(
            "practice",
            language=state["language"],
            instruction=SET_TASK_INSTRUCTION.format(interest=interest, concept_labels=labels),
            transcript="",
        )
        return {
            "stage": "practice",
            "stage_step": 1,
            "reply_text": reply,
            "ui": {"type": "request_photo", "prompt": reply},
        }

    transcript = state["transcript"] or ""
    if transcript.startswith(PHOTO_MARKER):
        reply = await ask_conversational(
            "practice",
            language=state["language"],
            instruction=REVIEW_INSTRUCTION.format(
                interest=interest,
                observations=transcript[len(PHOTO_MARKER):].strip(),
                notes=notes,
            ),
            transcript="",
        )
        return {"stage": "earn", "stage_step": 0, "reply_text": reply, "ui": {"type": "idle"}}

    if is_unclear(transcript):
        reply = await ask_conversational(
            "practice", language=state["language"], instruction=REASK_INSTRUCTION, transcript=""
        )
        return {
            "stage": "practice",
            "stage_step": 1,
            "reply_text": reply,
            "ui": {"type": "request_photo", "prompt": reply},
        }

    reply = await ask_conversational(
        "practice",
        language=state["language"],
        instruction=NO_PHOTO_INSTRUCTION,
        transcript=transcript,
    )
    return {"stage": "earn", "stage_step": 0, "reply_text": reply, "ui": {"type": "idle"}}
