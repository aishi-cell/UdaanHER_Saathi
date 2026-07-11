"""Placeholder assess node. Real story-questions + structured-output ProfileDraft arrive in T12."""

from app.agent.state import AgentState


async def run(state: AgentState) -> dict:
    return {
        "stage": "confirm_profile",
        "reply_text": "Bahut badhiya! Thoda aur bataiye apne kaam ke baare mein.",
        "ui": {"type": "idle"},
    }
