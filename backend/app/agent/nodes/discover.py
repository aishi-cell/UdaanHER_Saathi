"""Real discover node (T12): village+work, then interest via show_options.

The 4 skill cards are a placeholder set (tailoring, beauty, handicrafts,
cooking) since T15's curriculum JSON doesn't exist yet -- only tailoring
actually leads anywhere real downstream (T18+). See docs/decisions.md.
"""

from pydantic import BaseModel

from app.agent.llm_utils import ask_conversational, extract_structured, is_unclear
from app.agent.state import AgentState

SKILL_OPTIONS = [
    {"id": "tailoring", "label": "Tailoring", "image": "assets/skill_tailoring.png"},
    {"id": "beauty", "label": "Beauty", "image": "assets/skill_beauty.png"},
    {"id": "handicrafts", "label": "Handicrafts", "image": "assets/skill_handicrafts.png"},
    {"id": "cooking", "label": "Cooking", "image": "assets/skill_cooking.png"},
]
SKILL_LABELS = {opt["id"]: opt["label"] for opt in SKILL_OPTIONS}

ASK_VILLAGE_INSTRUCTION = (
    "Ask her which village or town she's from, and what work she does day to "
    "day right now -- one warm question covering both."
)
EXTRACT_VILLAGE_INSTRUCTION = (
    "Extract her village/town name and a short note on her current work from "
    "her reply. Her speech-to-text transcript may be imperfect, informal, "
    "code-mixed, or have a strong regional accent -- make your best "
    "reasonable guess rather than expecting a perfectly clean sentence."
)
REASK_VILLAGE_INSTRUCTION = (
    "You couldn't quite make out what she said. Warmly and briefly say you "
    "didn't catch that, and ask again which village or town she's from and "
    "what work she does -- no need to apologise much, this happens."
)
REASK_INTEREST_INSTRUCTION = (
    "You couldn't quite make out which skill she wants to learn. Warmly say "
    "you didn't catch that, and ask again -- she can tap a card or say it "
    "aloud."
)
ASK_INTEREST_INSTRUCTION = (
    "Thank her for sharing about her village and work. Now ask which skill "
    "she would like to learn -- she can see picture cards on screen, or just "
    "say it aloud."
)
ACK_INTEREST_INSTRUCTION = (
    "She just told you which skill she wants to learn: {interest_label}. "
    "React warmly and say you're excited to start getting to know what she "
    "already knows."
)


class VillageWorkExtraction(BaseModel):
    village: str
    work_notes: str


class InterestExtraction(BaseModel):
    option_id: str


async def run(state: AgentState) -> dict:
    profile = dict(state.get("profile") or {})
    step = state["stage_step"]

    if step == 0:
        # transcript is intentionally NOT forwarded here: it belongs to
        # greet's consent question, not this one. Passing it anyway lets the
        # LLM "helpfully" react to and jump ahead of it, which desyncs the
        # stage_step counter from what was actually asked (T12 postmortem:
        # a live run showed step1's village extraction running against
        # "tailoring" because step0 had already improvised straight to the
        # interest question).
        reply = await ask_conversational(
            "discover",
            language=state["language"],
            instruction=ASK_VILLAGE_INSTRUCTION,
            transcript="",
        )
        return {"stage": "discover", "stage_step": 1, "reply_text": reply, "ui": {"type": "idle"}}

    if step == 1:
        if is_unclear(state["transcript"]):
            reply = await ask_conversational(
                "discover",
                language=state["language"],
                instruction=REASK_VILLAGE_INSTRUCTION,
                transcript="",
            )
            return {
                "stage": "discover",
                "stage_step": 1,
                "reply_text": reply,
                "ui": {"type": "idle"},
            }

        extraction = await extract_structured(
            "discover",
            language=state["language"],
            instruction=EXTRACT_VILLAGE_INSTRUCTION,
            transcript=state["transcript"],
            schema=VillageWorkExtraction,
        )
        profile["village"] = extraction.village
        profile["notes"] = extraction.work_notes
        reply = await ask_conversational(
            "discover",
            language=state["language"],
            instruction=ASK_INTEREST_INSTRUCTION,
            transcript=state["transcript"],
        )
        return {
            "stage": "discover",
            "stage_step": 2,
            "profile": profile,
            "reply_text": reply,
            "ui": {"type": "show_options", "prompt": reply, "options": SKILL_OPTIONS},
        }

    # step == 2: she answered the interest question, by tap or by voice.
    # A tap arrives as the bare option id; voice arrives as a real transcript,
    # which will essentially never equal one of our short id strings exactly.
    if state["transcript"] in SKILL_LABELS:
        option_id = state["transcript"]
    elif is_unclear(state["transcript"]):
        reply = await ask_conversational(
            "discover",
            language=state["language"],
            instruction=REASK_INTEREST_INSTRUCTION,
            transcript="",
        )
        return {"stage": "discover", "stage_step": 2, "reply_text": reply, "ui": {"type": "idle"}}
    else:
        extraction = await extract_structured(
            "discover",
            language=state["language"],
            instruction=(
                "From her reply, work out which of these skills she means: "
                + ", ".join(f"{k} ({v})" for k, v in SKILL_LABELS.items())
                + ". Answer with the exact id. Her speech-to-text transcript "
                "may be imperfect, informal, code-mixed, or have a strong "
                "regional accent -- make your best reasonable guess."
            ),
            transcript=state["transcript"],
            schema=InterestExtraction,
        )
        option_id = extraction.option_id if extraction.option_id in SKILL_LABELS else "tailoring"

    profile["interest"] = option_id
    reply = await ask_conversational(
        "discover",
        language=state["language"],
        instruction=ACK_INTEREST_INSTRUCTION.format(interest_label=SKILL_LABELS[option_id]),
        transcript=state["transcript"],
    )
    return {
        "stage": "assess",
        "stage_step": 0,
        "profile": profile,
        "reply_text": reply,
        "ui": {"type": "idle"},
    }
