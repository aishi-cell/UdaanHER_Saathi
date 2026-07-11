"""Placeholder close node. Real final-save + session ended_at arrives in T21.
Terminal: stays at close on any further turn."""

from app.agent.state import AgentState


async def run(state: AgentState) -> dict:
    return {
        "stage": "close",
        "reply_text": "Milte hain phir se, apna khayal rakhiyega!",
        "ui": {"type": "idle"},
    }
