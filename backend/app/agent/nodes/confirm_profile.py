"""Placeholder confirm_profile node. Real save-via-T09-repository-on-yes,
fix-on-no flow arrives in T12. For the skeleton, always "confirms" a canned
draft so downstream stages (which require a profile) are reachable."""

from app.agent.state import AgentState


async def run(state: AgentState) -> dict:
    profile = state.get("profile") or {
        "name": "Sunita",
        "village": "",
        "interest": "tailoring",
        "starting_level": "some",
        "notes": "",
    }
    return {
        "stage": "teach",
        "profile": profile,
        "reply_text": "Toh maine yeh samjha -- sahi hai kya? Chaliye aage badhte hain.",
        "ui": {
            "type": "show_profile_card",
            "profile": {
                "name": profile.get("name", ""),
                "village": profile.get("village", ""),
                "language": state["language"],
                "interest": profile.get("interest", ""),
                "starting_level": profile.get("starting_level", "some"),
                "notes": profile.get("notes", ""),
            },
        },
    }
