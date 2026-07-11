"""Placeholder reteach node. Real aid-selection-from-index and re-check
arrive in T20. Not reachable from the skeleton's viva node yet (no real
grading to trigger it); app.agent.guards.can_start_reteach already
enforces the 2-round cap for when T20 wires this up for real."""

from app.agent.state import AgentState


async def run(state: AgentState) -> dict:
    return {
        "stage": "viva",
        "reply_text": "Chaliye ise phir se samjhate hain, thoda alag tarike se.",
        "ui": {"type": "idle"},
    }
