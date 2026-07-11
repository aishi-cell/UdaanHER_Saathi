"""Placeholder discover node. Real show_options + village/work questions arrive in T12."""

from app.agent.state import AgentState


async def run(state: AgentState) -> dict:
    return {
        "stage": "assess",
        "reply_text": "Accha! Ab bataiye, aap kis kaam mein ruchi rakhti hain?",
        "ui": {"type": "idle"},
    }
