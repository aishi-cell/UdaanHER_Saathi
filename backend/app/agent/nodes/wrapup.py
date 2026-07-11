"""Placeholder wrapup node. Real show_progress payload from T09's
get_progress arrives in T21."""

from app.agent.state import AgentState


async def run(state: AgentState) -> dict:
    return {
        "stage": "close",
        "reply_text": "Aaj bahut accha kaam kiya aapne! Agli baar hum aage badhenge.",
        "ui": {"type": "idle"},
    }
