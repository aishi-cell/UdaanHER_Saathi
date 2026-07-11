"""Placeholder resume node. Real greeting-by-name-with-history and
jump-to-next-lesson arrive in T22. Called directly by POST /api/session
(via the graph's stage-based dispatch) when a returning learner's
name+PIN resolve to an existing row."""

from app.agent.state import AgentState


async def run(state: AgentState) -> dict:
    name = (state.get("profile") or {}).get("name", "")
    greeting = f"Wapas aane ke liye shukriya, {name}!" if name else "Wapas aane ke liye shukriya!"
    return {
        "stage": "teach",
        "reply_text": f"{greeting} Chaliye wahi se shuru karte hain jahan humne chhoda tha.",
        "ui": {"type": "idle"},
    }
