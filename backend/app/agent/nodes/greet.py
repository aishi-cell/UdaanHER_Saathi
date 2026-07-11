"""Placeholder greet node. Real persona-driven prompting arrives in T12."""

from app.agent.state import AgentState


async def run(state: AgentState) -> dict:
    return {
        "stage": "discover",
        "reply_text": "Namaste! Main aapki saathi hoon. Chaliye shuru karte hain -- aapka naam kya hai?",
        "ui": {"type": "idle"},
    }
