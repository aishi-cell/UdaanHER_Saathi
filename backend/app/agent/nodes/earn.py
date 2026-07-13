"""Earn node, plan v2 principle 1: the reason she is here.

Two spoken beats from the store's earning notes -- (1) what to make and what
it realistically sells for, (2) who buys and how the first customers come --
then hand over to wrapup. Content comes from the skill package's
EarningNotes, never invented, so rupee numbers stay grounded in what the
builder distilled (or a human wrote).
"""

from app.agent.llm_utils import ask_conversational
from app.agent.state import AgentState
from app.agent.teaching_utils import load_package

PRODUCTS_INSTRUCTION = (
    "Now the part she came for: earning from {interest}. From these notes, "
    "tell her -- concretely, with real rupee amounts -- what she can start "
    "making or offering and what it earns:\n{products}\n{pricing_notes}\n\n"
    "Pick the 1-2 easiest starting points for a beginner, don't list "
    "everything. End by asking if she'd like to hear how the first "
    "customers come."
)
CUSTOMERS_INSTRUCTION = (
    "Tell her, from these notes, who her first customers will be and how to "
    "find them -- concrete and local, starting from her own street:\n"
    "{customer_notes}\n\nEnd warmly: the first one is the hardest, after "
    "that the work speaks for itself. Then say you two will take one last "
    "look at everything she did today."
)


async def run(state: AgentState) -> dict:
    package = load_package(state)
    if package is None:
        return {
            "stage": "wrapup",
            "stage_step": 0,
            "reply_text": "Chaliye dekhte hain aaj humne kya kya kiya.",
            "ui": {"type": "idle"},
        }

    earning = package.curriculum.earning
    interest = (state.get("profile") or {}).get("interest", "this skill")

    if state["stage_step"] == 0:
        reply = await ask_conversational(
            "earn",
            language=state["language"],
            instruction=PRODUCTS_INSTRUCTION.format(
                interest=interest,
                products="\n".join(f"- {p}" for p in earning.products),
                pricing_notes=earning.pricing_notes,
            ),
            transcript=state["transcript"],
        )
        return {"stage": "earn", "stage_step": 1, "reply_text": reply, "ui": {"type": "idle"}}

    reply = await ask_conversational(
        "earn",
        language=state["language"],
        instruction=CUSTOMERS_INSTRUCTION.format(customer_notes=earning.customer_notes),
        transcript=state["transcript"],
    )
    return {"stage": "wrapup", "stage_step": 0, "reply_text": reply, "ui": {"type": "idle"}}
