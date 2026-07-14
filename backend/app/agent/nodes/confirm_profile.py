"""Real confirm_profile node (T12): show_profile_card, read aloud, save on yes.

Consent (Spec S12): on a spoken/tapped yes to being remembered (greet sets
consent_declined), the learner row is only created here, once she has also
confirmed the profile is correct. On "no", the conversation still continues
normally but nothing is ever written to learners.
"""

import secrets
from datetime import datetime, timezone

from pydantic import BaseModel

from app.agent.llm_utils import ask_conversational, extract_structured, is_unclear
from app.agent.state import AgentState
from app.models import db as db_repo

READBACK_INSTRUCTION = (
    "Say back, warmly and briefly, what you understood: her name is {name}, "
    "she's from {village}, and she wants to learn {interest}. Ask if that's "
    "right."
)
EXTRACT_INSTRUCTION = (
    "Work out whether she confirmed the profile is correct, or is correcting "
    "something. If correcting, say which field (name, village, or interest) "
    "and the corrected value. Her speech-to-text transcript may be "
    "imperfect, informal, code-mixed, or have a strong regional accent -- "
    "make your best reasonable guess rather than expecting a perfectly "
    "clean sentence."
)
CORRECTED_INSTRUCTION = (
    "Thank her for the correction, confirm the updated detail back to her, "
    "and ask if everything is right now."
)
SAVED_INSTRUCTION = (
    "She confirmed everything is correct. Warmly say you're excited to start "
    "learning together. Then tell her, clearly and slowly, that her special "
    "number (PIN) is {pin_spoken} -- say each digit separately -- and that "
    "next time she only needs to say her name and these 4 digits to continue "
    "right where she left off. Ask her to keep it in mind."
)
NOT_SAVED_INSTRUCTION = (
    "She confirmed everything is correct, but earlier chose not to be "
    "remembered -- that's fine. Warmly say you're excited to start learning "
    "together today."
)
REASK_INSTRUCTION = (
    "You couldn't quite make out her answer. Warmly and briefly say you "
    "didn't catch that, and ask again if the profile shown is right -- no "
    "need to apologise much, this happens."
)


class ConfirmationExtraction(BaseModel):
    confirmed: bool
    corrected_field: str | None = None
    corrected_value: str | None = None


def _profile_card_ui(profile: dict, language: str) -> dict:
    return {
        "type": "show_profile_card",
        "profile": {
            "name": profile.get("name", ""),
            "village": profile.get("village", ""),
            "language": language,
            "interest": profile.get("interest", ""),
            "starting_level": profile.get("starting_level", "some"),
            "notes": profile.get("notes", ""),
        },
    }


async def run(state: AgentState) -> dict:
    profile = dict(state.get("profile") or {})

    if state["stage_step"] == 0:
        # transcript belongs to assess's last question, not this readback --
        # see the matching note in discover.py step 0.
        reply = await ask_conversational(
            "confirm_profile",
            language=state["language"],
            instruction=READBACK_INSTRUCTION.format(
                name=profile.get("name", ""),
                village=profile.get("village", ""),
                interest=profile.get("interest", ""),
            ),
            transcript="",
        )
        return {
            "stage": "confirm_profile",
            "stage_step": 1,
            "reply_text": reply,
            "ui": _profile_card_ui(profile, state["language"]),
        }

    if is_unclear(state["transcript"]):
        reply = await ask_conversational(
            "confirm_profile",
            language=state["language"],
            instruction=REASK_INSTRUCTION,
            transcript="",
        )
        return {
            "stage": "confirm_profile",
            "stage_step": 1,
            "reply_text": reply,
            "ui": _profile_card_ui(profile, state["language"]),
        }

    extraction = await extract_structured(
        "confirm_profile",
        language=state["language"],
        instruction=EXTRACT_INSTRUCTION,
        transcript=state["transcript"],
        schema=ConfirmationExtraction,
    )

    if not extraction.confirmed and extraction.corrected_field:
        if extraction.corrected_field in {"name", "village", "interest"} and extraction.corrected_value:
            profile[extraction.corrected_field] = extraction.corrected_value
        reply = await ask_conversational(
            "confirm_profile",
            language=state["language"],
            instruction=CORRECTED_INSTRUCTION,
            transcript=state["transcript"],
        )
        return {
            "stage": "confirm_profile",
            "stage_step": 0,
            "profile": profile,
            "reply_text": reply,
            "ui": {"type": "idle"},
        }

    learner_id = state.get("learner_id")
    saved_instruction = NOT_SAVED_INSTRUCTION
    if not state.get("consent_declined"):
        # Her PIN for return visits (T22): random 4 digits, spoken to her in
        # the confirmation reply -- greet's returning path looks it up by
        # name + these digits.
        pin = f"{secrets.randbelow(10_000):04d}"
        learner = db_repo.create_learner(
            name=profile.get("name", ""),
            village=profile.get("village"),
            language=state["language"],
            pin=pin,
            interest_skill=profile.get("interest"),
            starting_level=profile.get("starting_level"),
            notes=profile.get("notes"),
            consent_given_at=datetime.now(timezone.utc),
        )
        learner_id = learner.id
        db_repo.link_session_to_learner(state["session_id"], learner_id)
        saved_instruction = SAVED_INSTRUCTION.format(pin_spoken=" ".join(pin))

    reply = await ask_conversational(
        "confirm_profile",
        language=state["language"],
        instruction=saved_instruction,
        transcript=state["transcript"],
    )
    return {
        "stage": "teach",
        "stage_step": 0,
        "profile": profile,
        "learner_id": learner_id,
        "reply_text": reply,
        "ui": {"type": "idle"},
    }
