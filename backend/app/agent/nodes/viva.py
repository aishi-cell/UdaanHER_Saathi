"""Placeholder viva node. Real rubric questions + structured-output grading
arrive in T19. The skeleton always proceeds to wrapup since there is no real
grading yet to decide reteach vs wrapup."""

from app.agent.state import AgentState


async def run(state: AgentState) -> dict:
    return {
        "stage": "wrapup",
        "reply_text": "Ab thoda baat karte hain jo aapne seekha uske baare mein.",
        "ui": {"type": "idle"},
    }
