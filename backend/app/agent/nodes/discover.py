"""Discover node, plan v2: village+work, then "what do you want to earn from?"

The skill choice is open-ended (plan v2 principle 3 -- nothing hardcoded):
cards shown are whatever the content store holds, and she can name ANY skill
by voice. A named skill that is already in the store proceeds immediately; an
unseeded one kicks off a background Content Builder run (the slow lane) while
she is warmly offered what is ready today.
"""

from pydantic import BaseModel

from app.agent.llm_utils import ask_conversational, extract_structured, is_unclear
from app.agent.state import AgentState
from app.config import get_settings
from app.content import builder, store

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
    "you didn't catch that, and ask again -- she can tap a card or just name "
    "any work she'd like to earn from."
)
ASK_INTEREST_INSTRUCTION = (
    "Thank her for sharing about her village and work. Now ask what skill or "
    "work she would like to learn to EARN from -- she can tap one of the "
    "picture cards on screen, or simply name anything she has in mind, in "
    "her own words."
)
ACK_INTEREST_INSTRUCTION = (
    "She just told you which skill she wants to learn: {interest_label}. "
    "React warmly and say you're excited to start getting to know what she "
    "already knows about it."
)
BUILDING_INSTRUCTION = (
    "She asked to learn '{asked_label}'. That one is not ready yet -- you are "
    "putting it together for her and it will be ready soon. Tell her that "
    "warmly (never blame her), and invite her to begin today with one of the "
    "skills on the cards while hers gets prepared."
)


class VillageWorkExtraction(BaseModel):
    village: str
    work_notes: str


class SkillChoiceExtraction(BaseModel):
    matched_skill_id: str  # exact id from the available list, or "" if none fits
    skill_name_english: str  # short canonical English name for what she asked


def _cards(language: str) -> list[dict]:
    return store.skill_cards(language)


async def run(state: AgentState) -> dict:
    profile = dict(state.get("profile") or {})
    step = state["stage_step"]
    language = state["language"]

    if step == 0:
        # transcript is intentionally NOT forwarded here: it belongs to
        # greet's consent question, not this one. Passing it anyway lets the
        # LLM "helpfully" react to and jump ahead of it, which desyncs the
        # stage_step counter from what was actually asked (T12 postmortem).
        reply = await ask_conversational(
            "discover",
            language=language,
            instruction=ASK_VILLAGE_INSTRUCTION,
            transcript="",
        )
        return {"stage": "discover", "stage_step": 1, "reply_text": reply, "ui": {"type": "idle"}}

    if step == 1:
        if is_unclear(state["transcript"]):
            reply = await ask_conversational(
                "discover",
                language=language,
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
            language=language,
            instruction=EXTRACT_VILLAGE_INSTRUCTION,
            transcript=state["transcript"],
            schema=VillageWorkExtraction,
        )
        profile["village"] = extraction.village
        profile["notes"] = extraction.work_notes
        reply = await ask_conversational(
            "discover",
            language=language,
            instruction=ASK_INTEREST_INSTRUCTION,
            transcript=state["transcript"],
        )
        return {
            "stage": "discover",
            "stage_step": 2,
            "profile": profile,
            "reply_text": reply,
            "ui": {"type": "show_options", "prompt": reply, "options": _cards(language)},
        }

    # step == 2: she answered the skill question, by tap or by voice.
    available = store.list_skills()
    skill_id: str | None = None
    asked_label = ""

    if state["transcript"] in available:
        # A tap arrives as the bare option id.
        skill_id = state["transcript"]
    elif is_unclear(state["transcript"]):
        reply = await ask_conversational(
            "discover",
            language=language,
            instruction=REASK_INTEREST_INSTRUCTION,
            transcript="",
        )
        return {
            "stage": "discover",
            "stage_step": 2,
            "reply_text": reply,
            "ui": {"type": "show_options", "prompt": reply, "options": _cards(language)},
        }
    else:
        labels = {
            sid: store.pick_language(store.load_skill(sid).curriculum.title, "en-IN")
            for sid in available
        }
        extraction = await extract_structured(
            "discover",
            language=language,
            instruction=(
                "She was asked what skill she wants to learn to earn from. "
                "Available ready-made skills: "
                + (", ".join(f"{k} ({v})" for k, v in labels.items()) or "(none)")
                + ". If her reply means one of those, set matched_skill_id to that "
                "exact id; otherwise leave it empty. Always set skill_name_english "
                "to a short canonical English name for what she asked (e.g. "
                "'mehndi', 'pickle making'). Her speech-to-text transcript may be "
                "imperfect, informal, code-mixed, or have a strong regional accent "
                "-- make your best reasonable guess."
            ),
            transcript=state["transcript"],
            schema=SkillChoiceExtraction,
        )
        if extraction.matched_skill_id in available:
            skill_id = extraction.matched_skill_id
        else:
            asked_label = extraction.skill_name_english or state["transcript"]

    if skill_id is None:
        # Unseeded skill: fire the slow lane in the background (plan v2 --
        # never build on the hot path), and offer what is ready today.
        builder.start_background_build(
            builder.slugify(asked_label),
            asked_label,
            youtube_api_key=get_settings().youtube_api_key,
        )
        reply = await ask_conversational(
            "discover",
            language=language,
            instruction=BUILDING_INSTRUCTION.format(asked_label=asked_label),
            transcript="",
        )
        return {
            "stage": "discover",
            "stage_step": 2,
            "reply_text": reply,
            "ui": {"type": "show_options", "prompt": reply, "options": _cards(language)},
        }

    interest_label = store.pick_language(store.load_skill(skill_id).curriculum.title, language)
    profile["interest"] = skill_id
    reply = await ask_conversational(
        "discover",
        language=language,
        instruction=ACK_INTEREST_INSTRUCTION.format(interest_label=interest_label),
        transcript=state["transcript"],
    )
    return {
        "stage": "assess",
        "stage_step": 0,
        "skill_id": skill_id,
        "profile": profile,
        "reply_text": reply,
        "ui": {"type": "idle"},
    }
