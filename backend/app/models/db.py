import hashlib
import hmac
import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from sqlmodel import Field
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine, select

from app.config import get_settings

PIN_HASH_ITERATIONS = 100_000


def _new_id() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --- Tables (Spec S10) ---


class Learner(SQLModel, table=True):
    __tablename__ = "learners"

    id: str = Field(default_factory=_new_id, primary_key=True)
    name: str
    village: str | None = None
    language: str
    pin_hash: str
    interest_skill: str | None = None
    starting_level: str | None = None
    notes: str | None = None
    consent_given_at: datetime
    created_at: datetime = Field(default_factory=_now)


class Session(SQLModel, table=True):
    __tablename__ = "sessions"

    id: str = Field(default_factory=_new_id, primary_key=True)
    learner_id: str | None = Field(default=None, foreign_key="learners.id")
    language: str
    started_at: datetime = Field(default_factory=_now)
    ended_at: datetime | None = None


class Turn(SQLModel, table=True):
    __tablename__ = "turns"

    id: int | None = Field(default=None, primary_key=True)
    session_id: str = Field(foreign_key="sessions.id")
    role: str
    transcript: str | None = None
    ui_type: str
    stage: str
    latency_ms_total: int
    created_at: datetime = Field(default_factory=_now)


class LessonProgress(SQLModel, table=True):
    __tablename__ = "lesson_progress"

    learner_id: str = Field(foreign_key="learners.id", primary_key=True)
    lesson_id: str = Field(primary_key=True)
    status: str
    completed_at: datetime | None = None


class ConceptMastery(SQLModel, table=True):
    __tablename__ = "concept_mastery"

    learner_id: str = Field(foreign_key="learners.id", primary_key=True)
    concept_id: str = Field(primary_key=True)
    mastery: str
    last_checked_at: datetime = Field(default_factory=_now)
    reteach_count: int = Field(default=0)


# --- Engine / session plumbing ---

_engine = None


def configure_engine(database_url: str) -> None:
    """(Re)points the module-level engine. Production code never calls this
    directly -- it's here so tests can redirect persistence to a temp file
    instead of the real data/app.db."""
    global _engine
    if database_url.startswith("sqlite:///"):
        db_path = Path(database_url.removeprefix("sqlite:///"))
        db_path.parent.mkdir(parents=True, exist_ok=True)
    _engine = create_engine(database_url, connect_args={"check_same_thread": False})


def get_engine():
    global _engine
    if _engine is None:
        configure_engine(get_settings().database_url)
    return _engine


def init_db() -> None:
    SQLModel.metadata.create_all(get_engine())


@contextmanager
def get_db_session() -> Iterator[DbSession]:
    with DbSession(get_engine()) as session:
        yield session


# --- PIN hashing ---


def _hash_pin(pin: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, PIN_HASH_ITERATIONS)
    return f"{salt.hex()}:{digest.hex()}"


def _verify_pin(pin: str, pin_hash: str) -> bool:
    try:
        salt_hex, digest_hex = pin_hash.split(":")
    except ValueError:
        return False
    salt = bytes.fromhex(salt_hex)
    expected = hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, PIN_HASH_ITERATIONS)
    return hmac.compare_digest(expected.hex(), digest_hex)


# --- Repository functions (agent code never writes SQL directly) ---


def create_learner(
    *,
    name: str,
    village: str | None,
    language: str,
    pin: str,
    interest_skill: str | None,
    starting_level: str | None,
    notes: str | None,
    consent_given_at: datetime,
) -> Learner:
    learner = Learner(
        name=name,
        village=village,
        language=language,
        pin_hash=_hash_pin(pin),
        interest_skill=interest_skill,
        starting_level=starting_level,
        notes=notes,
        consent_given_at=consent_given_at,
    )
    with get_db_session() as db:
        db.add(learner)
        db.commit()
        db.refresh(learner)
    return learner


def get_learner_by_name_pin(name: str, pin: str) -> Learner | None:
    with get_db_session() as db:
        candidates = db.exec(select(Learner).where(Learner.name == name)).all()
    for learner in candidates:
        if _verify_pin(pin, learner.pin_hash):
            return learner
    return None


def save_profile(
    learner_id: str,
    *,
    interest_skill: str | None = None,
    starting_level: str | None = None,
    notes: str | None = None,
    village: str | None = None,
) -> Learner:
    with get_db_session() as db:
        learner = db.get(Learner, learner_id)
        if learner is None:
            raise ValueError(f"No learner with id {learner_id}")
        if interest_skill is not None:
            learner.interest_skill = interest_skill
        if starting_level is not None:
            learner.starting_level = starting_level
        if notes is not None:
            learner.notes = notes
        if village is not None:
            learner.village = village
        db.add(learner)
        db.commit()
        db.refresh(learner)
        return learner


def create_session(*, learner_id: str | None, language: str) -> Session:
    session_row = Session(learner_id=learner_id, language=language)
    with get_db_session() as db:
        db.add(session_row)
        db.commit()
        db.refresh(session_row)
    return session_row


def link_session_to_learner(session_id: str, learner_id: str) -> None:
    """Backfills sessions.learner_id once a profile is saved mid-conversation
    (T12) -- the session starts with no learner attached for a brand-new
    visitor."""
    with get_db_session() as db:
        session_row = db.get(Session, session_id)
        if session_row is None:
            raise ValueError(f"No session with id {session_id}")
        session_row.learner_id = learner_id
        db.add(session_row)
        db.commit()


def log_turn(
    *,
    session_id: str,
    role: str,
    transcript: str | None,
    ui_type: str,
    stage: str,
    latency_ms_total: int,
) -> Turn:
    turn = Turn(
        session_id=session_id,
        role=role,
        transcript=transcript,
        ui_type=ui_type,
        stage=stage,
        latency_ms_total=latency_ms_total,
    )
    with get_db_session() as db:
        db.add(turn)
        db.commit()
        db.refresh(turn)
    return turn


def upsert_lesson_progress(
    learner_id: str,
    lesson_id: str,
    status: str,
    completed_at: datetime | None = None,
) -> LessonProgress:
    with get_db_session() as db:
        existing = db.get(LessonProgress, (learner_id, lesson_id))
        if existing:
            existing.status = status
            existing.completed_at = completed_at
            db.add(existing)
            db.commit()
            db.refresh(existing)
            return existing

        progress = LessonProgress(
            learner_id=learner_id,
            lesson_id=lesson_id,
            status=status,
            completed_at=completed_at,
        )
        db.add(progress)
        db.commit()
        db.refresh(progress)
        return progress


def upsert_concept_mastery(
    learner_id: str,
    concept_id: str,
    mastery: str,
    reteach_count: int | None = None,
) -> ConceptMastery:
    with get_db_session() as db:
        existing = db.get(ConceptMastery, (learner_id, concept_id))
        if existing:
            existing.mastery = mastery
            existing.last_checked_at = _now()
            if reteach_count is not None:
                existing.reteach_count = reteach_count
            db.add(existing)
            db.commit()
            db.refresh(existing)
            return existing

        row = ConceptMastery(
            learner_id=learner_id,
            concept_id=concept_id,
            mastery=mastery,
            reteach_count=reteach_count or 0,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row


# lesson_progress.status ('in_progress'|'completed', Spec S10) uses a different
# vocabulary than ProgressPayload.lessons[].status ('done'|'current'|'locked',
# Spec S8). 'locked' can't be derived here -- it means "not yet started", which
# requires knowing the full lesson order from the curriculum (T18).
_LESSON_STATUS_TO_UI = {"in_progress": "current", "completed": "done"}


def get_progress(learner_id: str) -> dict:
    """Returns the ProgressPayload shape from Spec S8. `title`/`label`/`skill`/
    `next_step_text` stay placeholders until T18 wires the content loader in."""
    with get_db_session() as db:
        lessons = db.exec(
            select(LessonProgress).where(LessonProgress.learner_id == learner_id)
        ).all()
        concepts = db.exec(
            select(ConceptMastery).where(ConceptMastery.learner_id == learner_id)
        ).all()

    return {
        "skill": "",
        "lessons": [
            {
                "lesson_id": lesson.lesson_id,
                "title": lesson.lesson_id,
                "status": _LESSON_STATUS_TO_UI.get(lesson.status, lesson.status),
            }
            for lesson in lessons
        ],
        "concepts": [
            {
                "concept_id": concept.concept_id,
                "label": concept.concept_id,
                "mastery": concept.mastery,
            }
            for concept in concepts
        ],
        "next_step_text": "",
    }


def delete_learner(learner_id: str) -> None:
    with get_db_session() as db:
        for row in db.exec(
            select(ConceptMastery).where(ConceptMastery.learner_id == learner_id)
        ).all():
            db.delete(row)
        for row in db.exec(
            select(LessonProgress).where(LessonProgress.learner_id == learner_id)
        ).all():
            db.delete(row)

        sessions = db.exec(select(Session).where(Session.learner_id == learner_id)).all()
        for session_row in sessions:
            for turn in db.exec(select(Turn).where(Turn.session_id == session_row.id)).all():
                db.delete(turn)
            db.delete(session_row)

        learner = db.get(Learner, learner_id)
        if learner:
            db.delete(learner)

        db.commit()
