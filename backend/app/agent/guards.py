"""Hard rules from Spec S9.1, enforced in code rather than left to prompts."""

from app.agent.state import AgentState

MAX_RETEACH_ROUNDS = 2


def teach_requires_profile(state: AgentState) -> bool:
    """teach is unreachable until a profile row exists."""
    return state.get("profile") is not None


def can_start_reteach(concept_id: str, reteach_counts: dict[str, int]) -> bool:
    """After 2 failed re-teach rounds, the concept is marked 'revisit next
    session' and the agent moves on -- never a third drill."""
    return reteach_counts.get(concept_id, 0) < MAX_RETEACH_ROUNDS
