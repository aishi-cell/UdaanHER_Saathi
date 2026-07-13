"""Shared helpers for the teaching stages (teach/viva/reteach/earn/wrapup)."""

from app.agent.state import AgentState
from app.content import store


def load_package(state: AgentState) -> store.SkillPackage | None:
    skill_id = state.get("skill_id")
    if not skill_id or not store.has_skill(skill_id):
        return None
    return store.load_skill(skill_id)


def path_concept_ids(state: AgentState, package: store.SkillPackage) -> list[str]:
    """Her personalized path from assess; every concept if none was computed
    (e.g. seeded/resumed sessions from before the diagnosis ran)."""
    path = list(state.get("learning_path") or [])
    return path or [c.concept_id for c in package.curriculum.concepts]


def coverage_order(package: store.SkillPackage, concept_ids: list[str]) -> list[str]:
    """Viva/reteach coverage order: must_land concepts first (Spec S9.1
    spirit), otherwise curriculum order."""
    ordered = [c.concept_id for c in package.curriculum.concepts if c.concept_id in set(concept_ids)]
    must = {c.concept_id for c in package.curriculum.concepts if c.must_land}
    return [c for c in ordered if c in must] + [c for c in ordered if c not in must]


def persistable_learner_id(state: AgentState) -> str | None:
    """Learner id iff we are allowed to write to the database: she exists as
    a row and did not decline consent (Spec S12)."""
    if state.get("consent_declined"):
        return None
    return state.get("learner_id")
