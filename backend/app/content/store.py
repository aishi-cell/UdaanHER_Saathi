"""Generalized per-skill content store (plan v2, docs/app_plan_v2.md).

One directory per skill under content/store/<skill_id>/ holding three JSON
files -- curriculum.json, rubrics.json, visual_aids.json -- in one shared
shape. Builder-produced and hand-authored packages are interchangeable: the
teach/viva/reteach engine reads this shape and never names a skill.

Validated at startup (validate_all): a typo in JSON must fail the boot, not
the demo.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

# language code -> text, e.g. {"en-IN": "...", "hi-IN": "...", "gu-IN": "..."}
LangText = dict[str, str]


class ContentError(RuntimeError):
    """Invalid or missing content. Message always names file + field."""


def _repo_root() -> Path:
    # backend/app/content/store.py -> parents[3] == repo root
    return Path(__file__).resolve().parents[3]


_store_root_override: Path | None = None


def store_root() -> Path:
    return _store_root_override or (_repo_root() / "content" / "store")


def configure_store_root(path: str | Path | None) -> None:
    """Point the store somewhere else (tests use a tmp dir)."""
    global _store_root_override
    _store_root_override = Path(path) if path is not None else None


def pick_language(text: LangText, language: str) -> str:
    """Best-available string for a session language: exact match, then same
    base language (hi for hi-IN), then en-IN, then anything."""
    if not text:
        return ""
    if language in text:
        return text[language]
    base = language.split("-")[0]
    for code, value in text.items():
        if code.split("-")[0] == base:
            return value
    return text.get("en-IN") or next(iter(text.values()))


# ---------------------------------------------------------------------------
# Models (the one shared shape)
# ---------------------------------------------------------------------------


class Concept(BaseModel):
    concept_id: str
    label: LangText
    must_land: bool = False


class MicroStep(BaseModel):
    """One spoken teaching beat (30-90s). `image` is an optional aid -- voice
    is the interface (plan v2 principle 2), so a step must work without it."""

    step_index: int
    concept_id: str
    teaching_notes: str  # written for the LLM, in English
    caption: LangText = Field(default_factory=dict)
    image: str | None = None


class EarningNotes(BaseModel):
    """Why she is here (plan v2 principle 1): make -> price -> sell."""

    products: list[str]  # what to make that actually sells, in English for the LLM
    pricing_notes: str  # what it sells for, material cost, margin -- for the LLM
    customer_notes: str  # who buys and where to find them -- for the LLM


class SkillCurriculum(BaseModel):
    skill_id: str
    title: LangText
    card_image: str | None = None  # optional option-card image for discover
    concepts: list[Concept]
    steps: list[MicroStep]
    common_mistakes: list[str] = Field(default_factory=list)
    earning: EarningNotes
    # Provenance: which real tutorials this was distilled from (grounded, not
    # invented). Empty only for hand-authored packages.
    source_video_ids: list[str] = Field(default_factory=list)
    # Human-reviewed content. Builder output starts False; a person flips it.
    trusted: bool = False


class RubricQuestion(BaseModel):
    question_id: str
    concept_id: str
    question: str  # phrased as friendly conversation, in English for the LLM
    sounds_right: list[str]  # spoken-style exemplars, informal / code-mixed
    sounds_confused: list[str]


class SkillRubrics(BaseModel):
    skill_id: str
    questions: list[RubricQuestion]


class VisualAid(BaseModel):
    concept_id: str
    kind: Literal["video", "diagram"]
    url_or_path: str  # youtube.com/embed/<id> or assets/... or data: URI
    language: str = "any"  # "hi-IN" | "gu-IN" | "any" | ...
    note: str = ""


class SkillPackage(BaseModel):
    curriculum: SkillCurriculum
    rubrics: SkillRubrics
    visual_aids: list[VisualAid] = Field(default_factory=list)

    @property
    def skill_id(self) -> str:
        return self.curriculum.skill_id

    def concept(self, concept_id: str) -> Concept | None:
        for c in self.curriculum.concepts:
            if c.concept_id == concept_id:
                return c
        return None

    def steps_for_concepts(self, concept_ids: list[str]) -> list[MicroStep]:
        """Curriculum-ordered steps whose concept is in the given set."""
        wanted = set(concept_ids)
        return [s for s in self.curriculum.steps if s.concept_id in wanted]

    def questions_for_concept(self, concept_id: str) -> list[RubricQuestion]:
        return [q for q in self.rubrics.questions if q.concept_id == concept_id]

    def aids_for_concept(self, concept_id: str, language: str) -> list[VisualAid]:
        """Aids for a concept, preferred language first, then Hindi, then any."""

        def rank(aid: VisualAid) -> int:
            if aid.language == language:
                return 0
            if aid.language.startswith("hi"):
                return 1
            if aid.language == "any":
                return 2
            return 3

        aids = [a for a in self.visual_aids if a.concept_id == concept_id]
        return sorted(aids, key=rank)


# ---------------------------------------------------------------------------
# IO
# ---------------------------------------------------------------------------

_FILES = {
    "curriculum": ("curriculum.json", SkillCurriculum),
    "rubrics": ("rubrics.json", SkillRubrics),
}


def list_skills(*, include_untrusted: bool = False) -> list[str]:
    """Teachable skills. Builder output starts trusted=false and stays
    invisible here until a human reviews it (decisions.md 2026-07-13) --
    a live session once offered an unreviewed auto-built skill as a card.
    Pass include_untrusted=True only for review tooling."""
    root = store_root()
    if not root.exists():
        return []
    ids = sorted(
        d.name for d in root.iterdir() if d.is_dir() and (d / "curriculum.json").exists()
    )
    if include_untrusted:
        return ids
    trusted = []
    for skill_id in ids:
        try:
            if load_skill(skill_id).curriculum.trusted:
                trusted.append(skill_id)
        except ContentError:
            continue  # invalid packages are surfaced by validate_all, not here
    return trusted


def package_exists(skill_id: str) -> bool:
    """Raw store presence, trusted or not -- the builder's dedupe check."""
    return (store_root() / skill_id / "curriculum.json").exists()


def has_skill(skill_id: str) -> bool:
    """True only for teachable (trusted) skills -- defense in depth so a
    stale learner row pointing at an unreviewed build never reaches teach."""
    return skill_id in list_skills()


def _load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ContentError(f"{path}: file missing") from None
    except json.JSONDecodeError as exc:
        raise ContentError(f"{path}: invalid JSON ({exc})") from None


def _validation_message(path: Path, exc: ValidationError) -> str:
    first = exc.errors()[0]
    loc = ".".join(str(p) for p in first["loc"])
    return f"{path}: field '{loc}': {first['msg']}"


def load_skill(skill_id: str) -> SkillPackage:
    skill_dir = store_root() / skill_id

    parsed: dict[str, object] = {}
    for key, (filename, model) in _FILES.items():
        path = skill_dir / filename
        try:
            parsed[key] = model.model_validate(_load_json(path))
        except ValidationError as exc:
            raise ContentError(_validation_message(path, exc)) from None

    aids_path = skill_dir / "visual_aids.json"
    aids: list[VisualAid] = []
    if aids_path.exists():
        try:
            aids = [VisualAid.model_validate(item) for item in _load_json(aids_path)]
        except ValidationError as exc:
            raise ContentError(_validation_message(aids_path, exc)) from None

    package = SkillPackage(curriculum=parsed["curriculum"], rubrics=parsed["rubrics"], visual_aids=aids)
    _cross_check(skill_dir, package)
    return package


def _cross_check(skill_dir: Path, package: SkillPackage) -> None:
    concept_ids = {c.concept_id for c in package.curriculum.concepts}
    for step in package.curriculum.steps:
        if step.concept_id not in concept_ids:
            raise ContentError(
                f"{skill_dir / 'curriculum.json'}: step {step.step_index} names "
                f"unknown concept_id '{step.concept_id}'"
            )
    for q in package.rubrics.questions:
        if q.concept_id not in concept_ids:
            raise ContentError(
                f"{skill_dir / 'rubrics.json'}: question '{q.question_id}' names "
                f"unknown concept_id '{q.concept_id}'"
            )
    for aid in package.visual_aids:
        if aid.concept_id not in concept_ids:
            raise ContentError(
                f"{skill_dir / 'visual_aids.json'}: aid names unknown "
                f"concept_id '{aid.concept_id}'"
            )
    for concept_id in concept_ids:
        if not package.questions_for_concept(concept_id):
            raise ContentError(
                f"{skill_dir / 'rubrics.json'}: concept '{concept_id}' has no "
                "viva questions"
            )


def save_skill(package: SkillPackage) -> Path:
    skill_dir = store_root() / package.skill_id
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "curriculum.json").write_text(
        package.curriculum.model_dump_json(indent=2), encoding="utf-8"
    )
    (skill_dir / "rubrics.json").write_text(
        package.rubrics.model_dump_json(indent=2), encoding="utf-8"
    )
    (skill_dir / "visual_aids.json").write_text(
        json.dumps([a.model_dump() for a in package.visual_aids], indent=2),
        encoding="utf-8",
    )
    return skill_dir


def validate_all() -> list[str]:
    """Load every cached skill; raise ContentError on the first bad one.
    Called at startup: fail loud, not in front of Sunita."""
    skills = list_skills(include_untrusted=True)
    for skill_id in skills:
        load_skill(skill_id)
    return skills


def skill_cards(language: str) -> list[dict]:
    """Option cards for discover, built from the seeded store -- never
    hardcoded skills (plan v2 principle 3)."""
    cards = []
    for skill_id in list_skills():
        curriculum = load_skill(skill_id).curriculum
        cards.append(
            {
                "id": skill_id,
                "label": pick_language(curriculum.title, language),
                "image": curriculum.card_image or "assets/skill_generic.svg",
            }
        )
    return cards
