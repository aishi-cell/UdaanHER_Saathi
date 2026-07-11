"""Placeholder teach node. Real step-by-step lesson narration from content
JSON arrives in T18. teach is unreachable without a profile (Spec S9.1) --
the graph's router already enforces this (app/agent/graph.py), this check
is a defensive second layer."""

from app.agent.guards import teach_requires_profile
from app.agent.state import AgentState


async def run(state: AgentState) -> dict:
    if not teach_requires_profile(state):
        return {
            "stage": "confirm_profile",
            "reply_text": "Pehle mujhe thoda aur jaanna hoga aapke baare mein.",
            "ui": {"type": "idle"},
        }

    return {
        "stage": "viva",
        "reply_text": "Chaliye, pehla step dekhte hain.",
        "ui": {"type": "idle"},
    }
