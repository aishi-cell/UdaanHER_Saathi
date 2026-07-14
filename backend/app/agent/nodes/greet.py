"""Real greet node (T12 + T22): welcome, and branch new vs returning.

step 0  welcome; ask her name and whether you two have talked before
step 1  extract {name, returning}
          new       -> ask spoken consent to be remembered      (-> step 2)
          returning -> ask for her 4-digit PIN                  (-> step 3)
step 2  extract consent yes/no, ack, hand off to discover
step 3  extract spoken PIN -> lookup name+PIN
          match -> welcome back + resume at her next gap (resume helpers)
          miss  -> one gentle retry                             (-> step 4)
step 4  second PIN attempt; a second miss starts her fresh (consent ask,
        -> step 2) -- never a dead end, never blame her
"""

from pydantic import BaseModel, Field

from app.agent.llm_utils import ask_conversational, extract_structured, is_unclear
from app.agent.nodes.resume import (
    WELCOME_BACK_INSTRUCTION,
    PROGRESS_LINE_SOME_DONE,
    PROGRESS_LINE_FRESH,
    build_resume_updates,
    profile_from_learner,
)
from app.agent.state import AgentState
from app.models import db as db_repo

ASK_INSTRUCTION = (
    "Welcome her warmly. Ask her name. In the same breath, ask plainly "
    "whether the two of you have talked before -- e.g. 'Have we met before, "
    "or is this your first time here?'"
)
EXTRACT_INSTRUCTION = (
    "She just answered your greeting. From her reply, work out her name and "
    "whether she says you two have talked before (she is a RETURNING "
    "visitor) or this is her first time.\n\n"
    "Her speech-to-text transcript may be imperfect, informal, code-mixed, or "
    "have a strong regional accent -- she is not expected to speak "
    "'textbook' language. Make your best reasonable guess from what's there "
    "rather than expecting a perfectly clean sentence. When genuinely unsure "
    "whether she is returning, treat her as new -- a fresh start is warmer "
    "than asking a stranger for a PIN."
)
REASK_INSTRUCTION = (
    "You couldn't quite make out what she said. Warmly and briefly say you "
    "didn't catch that, and ask her name and whether you two have talked "
    "before again, in a relaxed way -- no need to apologise much, this "
    "happens."
)
ASK_CONSENT_INSTRUCTION = (
    "Her name is {name} and this is her first visit. Ask plainly whether she "
    "wants you to remember her for next time -- e.g. 'Shall I remember you, "
    "so next time we continue where we left off?'"
)
REASK_CONSENT_INSTRUCTION = (
    "You couldn't quite make out her answer. Warmly and briefly ask again "
    "whether she'd like to be remembered for next time -- no need to "
    "apologise much, this happens."
)
CONSENT_EXTRACT_INSTRUCTION = (
    "Work out whether she agreed to be remembered (a plain yes/no, spoken "
    "any way she likes -- 'haan', 'ha', 'nahi', silence-then-hesitation "
    "counts as no). Her transcript may be imperfect, informal, or code-mixed "
    "-- best reasonable guess."
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
ASK_PIN_INSTRUCTION = (
    "Lovely -- she says you two have met before. Ask her to say her 4-digit "
    "PIN, the one you gave her when you first met, one digit at a time."
)
RETRY_PIN_INSTRUCTION = (
    "The PIN she said didn't match what you have for {name}. Gently -- never "
    "blaming her -- say it didn't match and ask her to say the 4 digits once "
    "more, slowly, one at a time."
)
REASK_PIN_INSTRUCTION = (
    "You couldn't quite make out the digits. Warmly ask her to say her "
    "4-digit PIN once more, slowly, one digit at a time."
)
FRESH_START_INSTRUCTION = (
    "The PIN didn't match again -- never mind, and never make her feel at "
    "fault. Warmly say it's no problem at all, you two will simply start "
    "fresh today. Then ask plainly whether she wants you to remember her "
    "for next time."
)
PIN_EXTRACT_INSTRUCTION = (
    "She just spoke her 4-digit PIN. She may say the digits in any language "
    "(Hindi, Gujarati, English), as words or numbers, possibly with filler "
    "around them. Output ONLY the digits you heard, in order, as a string "
    "like '4271'. If you cannot make out 4 digits, output what you heard."
)


class GreetExtraction(BaseModel):
    name: str
    returning: bool = Field(
        description="true ONLY if she clearly says you two have talked before"
    )


class ConsentExtraction(BaseModel):
    consent_given: bool


class PinExtraction(BaseModel):
    pin: str


def _idle(reply: str, *, stage_step: int, **extra) -> dict:
    return {
        "stage": "greet",
        "stage_step": stage_step,
        "reply_text": reply,
        "ui": {"type": "idle"},
        **extra,
    }


async def _ask(state: AgentState, instruction: str, *, transcript: str | None = None) -> str:
    return await ask_conversational(
        "greet",
        language=state["language"],
        instruction=instruction,
        transcript=state["transcript"] if transcript is None else transcript,
    )


async def _handle_pin_attempt(state: AgentState, *, attempts_left: int) -> dict:
    name = (state.get("profile") or {}).get("name", "")
    this_step = 4 - attempts_left  # step 3 has one retry left, step 4 none

    if is_unclear(state["transcript"]):
        return _idle(await _ask(state, REASK_PIN_INSTRUCTION), stage_step=this_step)

    extraction = await extract_structured(
        "greet",
        language=state["language"],
        instruction=PIN_EXTRACT_INSTRUCTION,
        transcript=state["transcript"],
        schema=PinExtraction,
    )
    # Normalize any Unicode digits (Devanagari/Gujarati numerals) to ASCII.
    pin = "".join(str(int(ch)) for ch in extraction.pin if ch.isdigit())
    # PIN-first lookup: her spoken name may arrive in a different script
    # than it was saved in, so it's a tiebreaker, not a filter.
    learner = db_repo.find_learner_by_pin(pin, name_hint=name) if len(pin) == 4 else None

    if learner is not None:
        updates = build_resume_updates(
            {**state, "learner_id": learner.id, "skill_id": learner.interest_skill or None}
        )
        db_repo.link_session_to_learner(state["session_id"], learner.id)
        remaining = len(updates["learning_path"])
        mastered_any = bool(db_repo.get_mastery_map(learner.id))
        progress_line = (
            PROGRESS_LINE_SOME_DONE.format(remaining=remaining)
            if mastered_any and remaining
            else PROGRESS_LINE_FRESH
        )
        reply = await _ask(
            state,
            WELCOME_BACK_INSTRUCTION.format(
                name=learner.name,
                interest=learner.interest_skill or "her skill",
                progress_line=progress_line,
            ),
        )
        return {
            **updates,
            "learner_id": learner.id,
            "skill_id": learner.interest_skill or None,
            "profile": profile_from_learner(learner),
            "consent_declined": False,
            "reply_text": reply,
        }

    if attempts_left > 0:
        return _idle(
            await _ask(state, RETRY_PIN_INSTRUCTION.format(name=name)), stage_step=4
        )
    # Second miss: start her fresh -- back onto the new-visitor consent path.
    return _idle(await _ask(state, FRESH_START_INSTRUCTION), stage_step=2)


async def run(state: AgentState) -> dict:
    step = state["stage_step"]

    if step == 0:
        # Not "" -- ask_conversational renders that as "(no speech was heard
        # clearly)", and a live run showed the model then apologising for
        # unclear audio in the very first words of the session.
        return _idle(
            await _ask(
                state, ASK_INSTRUCTION, transcript="(she has just arrived; nothing spoken yet)"
            ),
            stage_step=1,
        )

    if step == 1:
        if is_unclear(state["transcript"]):
            return _idle(await _ask(state, REASK_INSTRUCTION), stage_step=1)
        extraction = await extract_structured(
            "greet",
            language=state["language"],
            instruction=EXTRACT_INSTRUCTION,
            transcript=state["transcript"],
            schema=GreetExtraction,
        )
        profile = {"name": extraction.name}
        if extraction.returning:
            return _idle(
                await _ask(state, ASK_PIN_INSTRUCTION), stage_step=3, profile=profile
            )
        return _idle(
            await _ask(state, ASK_CONSENT_INSTRUCTION.format(name=extraction.name)),
            stage_step=2,
            profile=profile,
        )

    if step == 2:
        if is_unclear(state["transcript"]):
            return _idle(await _ask(state, REASK_CONSENT_INSTRUCTION), stage_step=2)
        extraction = await extract_structured(
            "greet",
            language=state["language"],
            instruction=CONSENT_EXTRACT_INSTRUCTION,
            transcript=state["transcript"],
            schema=ConsentExtraction,
        )
        ack = ACK_INSTRUCTION_YES if extraction.consent_given else ACK_INSTRUCTION_NO
        reply = await _ask(state, ack)
        return {
            "stage": "discover",
            "stage_step": 0,
            "consent_declined": not extraction.consent_given,
            "reply_text": reply,
            "ui": {"type": "idle"},
        }

    # steps 3 and 4: her spoken PIN (first attempt, then one retry)
    return await _handle_pin_attempt(state, attempts_left=4 - step)
