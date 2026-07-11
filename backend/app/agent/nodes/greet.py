"""Real greet node (T12): welcome, ask name + spoken consent, extract on reply."""

from pydantic import BaseModel

from app.agent.llm_utils import ask_conversational, extract_structured, is_unclear
from app.agent.state import AgentState

ASK_INSTRUCTION = (
    "Welcome her warmly. Ask her name. In the same breath, ask plainly whether "
    "she wants you to remember her for next time -- e.g. 'Shall I remember you, "
    "so next time we continue where we left off?'"
)
EXTRACT_INSTRUCTION = (
    "She just answered your greeting. From her reply, work out her name and "
    "whether she agreed to be remembered (a plain yes/no, spoken any way she "
    "likes -- 'haan', 'ha', 'nahi', silence-then-hesitation counts as no).\n\n"
    "Her speech-to-text transcript may be imperfect, informal, code-mixed, or "
    "have a strong regional accent -- she is not expected to speak "
    "'textbook' language. Make your best reasonable guess from what's there "
    "rather than expecting a perfectly clean sentence."
)
REASK_INSTRUCTION = (
    "You couldn't quite make out what she said. Warmly and briefly say you "
    "didn't catch that, and ask her name and whether she'd like to be "
    "remembered again, in a relaxed way -- no need to apologise much, this "
    "happens."
)
ACK_INSTRUCTION_YES = (
    "She agreed to be remembered and told you her name. Thank her warmly by "
    "name, and say you're moving on to get to know her a little."
)
ACK_INSTRUCTION_NO = (
    "She said no to being remembered -- that's completely fine and her choice. "
    "Reassure her warmly that you'll still chat together today, then say "
    "you're moving on to get to know her a little."
)


class GreetExtraction(BaseModel):
    name: str
    consent_given: bool


async def run(state: AgentState) -> dict:
    if state["stage_step"] == 0:
        reply = await ask_conversational(
            "greet",
            language=state["language"],
            instruction=ASK_INSTRUCTION,
            transcript=state["transcript"],
        )
        return {"stage": "greet", "stage_step": 1, "reply_text": reply, "ui": {"type": "idle"}}

    if is_unclear(state["transcript"]):
        reply = await ask_conversational(
            "greet",
            language=state["language"],
            instruction=REASK_INSTRUCTION,
            transcript=state["transcript"],
        )
        return {"stage": "greet", "stage_step": 1, "reply_text": reply, "ui": {"type": "idle"}}

    extraction = await extract_structured(
        "greet",
        language=state["language"],
        instruction=EXTRACT_INSTRUCTION,
        transcript=state["transcript"],
        schema=GreetExtraction,
    )
    ack_instruction = ACK_INSTRUCTION_YES if extraction.consent_given else ACK_INSTRUCTION_NO
    reply = await ask_conversational(
        "greet",
        language=state["language"],
        instruction=ack_instruction,
        transcript=state["transcript"],
    )
    return {
        "stage": "discover",
        "stage_step": 0,
        "profile": {"name": extraction.name},
        "consent_declined": not extraction.consent_given,
        "reply_text": reply,
        "ui": {"type": "idle"},
    }
