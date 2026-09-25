from datetime import datetime, timezone

import pytest

from app.models import db


@pytest.fixture(autouse=True)
def temp_db(tmp_path):
    db.configure_engine(f"sqlite:///{tmp_path / 'test.db'}")
    db.init_db()
    yield
    db._engine = None


def _consent_now() -> datetime:
    return datetime.now(timezone.utc)


def test_create_and_fetch_learner_by_name_pin():
    learner = db.create_learner(
        name="Sunita",
        village="Rampur",
        language="gu-IN",
        pin="1234",
        interest_skill="tailoring",
        starting_level="some",
        notes=None,
        consent_given_at=_consent_now(),
    )

    found = db.get_learner_by_name_pin("Sunita", "1234")

    assert found is not None
    assert found.id == learner.id
    assert found.village == "Rampur"


def test_wrong_pin_never_returns_learner():
    db.create_learner(
        name="Sunita",
        village=None,
        language="gu-IN",
        pin="1234",
        interest_skill=None,
        starting_level=None,
        notes=None,
        consent_given_at=_consent_now(),
    )

    assert db.get_learner_by_name_pin("Sunita", "0000") is None
    assert db.get_learner_by_name_pin("NoSuchName", "1234") is None


def test_save_profile_updates_fields():
    learner = db.create_learner(
        name="Meena",
        village=None,
        language="hi-IN",
        pin="4321",
        interest_skill=None,
        starting_level=None,
        notes=None,
        consent_given_at=_consent_now(),
    )

    updated = db.save_profile(learner.id, interest_skill="tailoring", starting_level="new")

    assert updated.interest_skill == "tailoring"
    assert updated.starting_level == "new"


def test_log_turn_and_progress_roundtrip():
    learner = db.create_learner(
        name="Priya",
        village=None,
        language="gu-IN",
        pin="1111",
        interest_skill="tailoring",
        starting_level="some",
        notes=None,
        consent_given_at=_consent_now(),
    )
    session = db.create_session(learner_id=learner.id, language="gu-IN")

    turn = db.log_turn(
        session_id=session.id,
        role="user",
        transcript="hi",
        ui_type="idle",
        stage="greet",
        latency_ms_total=120,
    )
    assert turn.id is not None

    db.upsert_lesson_progress(learner.id, "tail-01-measure", "in_progress")
    db.upsert_concept_mastery(learner.id, "c-body-measure", "strong")

    progress = db.get_progress(learner.id)

    assert progress["lessons"] == [
        {"lesson_id": "tail-01-measure", "title": "tail-01-measure", "status": "current"}
    ]
    assert progress["concepts"] == [
        {"concept_id": "c-body-measure", "label": "c-body-measure", "mastery": "strong"}
    ]


def test_upsert_lesson_progress_updates_not_duplicates():
    learner = db.create_learner(
        name="Radha",
        village=None,
        language="gu-IN",
        pin="2222",
        interest_skill=None,
        starting_level=None,
        notes=None,
        consent_given_at=_consent_now(),
    )

    db.upsert_lesson_progress(learner.id, "tail-01-measure", "in_progress")
    db.upsert_lesson_progress(learner.id, "tail-01-measure", "completed")

    progress = db.get_progress(learner.id)
    assert len(progress["lessons"]) == 1
    assert progress["lessons"][0]["status"] == "done"


def test_upsert_concept_mastery_updates_not_duplicates():
    learner = db.create_learner(
        name="Geeta",
        village=None,
        language="gu-IN",
        pin="5555",
        interest_skill=None,
        starting_level=None,
        notes=None,
        consent_given_at=_consent_now(),
    )

    db.upsert_concept_mastery(learner.id, "c-body-measure", "shaky")
    db.upsert_concept_mastery(learner.id, "c-body-measure", "strong")

    progress = db.get_progress(learner.id)
    assert len(progress["concepts"]) == 1
    assert progress["concepts"][0]["mastery"] == "strong"


def test_delete_learner_cascades_everywhere():
    learner = db.create_learner(
        name="Kavita",
        village=None,
        language="gu-IN",
        pin="3333",
        interest_skill="tailoring",
        starting_level="some",
        notes=None,
        consent_given_at=_consent_now(),
    )
    session = db.create_session(learner_id=learner.id, language="gu-IN")
    db.log_turn(
        session_id=session.id,
        role="user",
        transcript="hi",
        ui_type="idle",
        stage="greet",
        latency_ms_total=100,
    )
    db.upsert_lesson_progress(learner.id, "tail-01-measure", "in_progress")
    db.upsert_concept_mastery(learner.id, "c-body-measure", "shaky")
    db.mark_milestone(learner.id, "tailoring", "started_skill")

    db.delete_learner(learner.id)

    with db.get_db_session() as s:
        assert s.get(db.Learner, learner.id) is None
        assert s.exec(db.select(db.Session).where(db.Session.learner_id == learner.id)).all() == []
        assert (
            s.exec(db.select(db.Turn).where(db.Turn.session_id == session.id)).all() == []
        )
        assert (
            s.exec(
                db.select(db.CareerMilestone).where(db.CareerMilestone.learner_id == learner.id)
            ).all()
            == []
        )
        assert (
            s.exec(
                db.select(db.LessonProgress).where(db.LessonProgress.learner_id == learner.id)
            ).all()
            == []
        )
        assert (
            s.exec(
                db.select(db.ConceptMastery).where(db.ConceptMastery.learner_id == learner.id)
            ).all()
            == []
        )


def test_mark_milestone_is_idempotent_and_scoped_per_skill():
    learner = db.create_learner(
        name="Kavita",
        village=None,
        language="gu-IN",
        pin="4444",
        interest_skill="tailoring",
        starting_level="some",
        notes=None,
        consent_given_at=_consent_now(),
    )

    first = db.mark_milestone(learner.id, "tailoring", "started_skill")
    again = db.mark_milestone(learner.id, "tailoring", "started_skill")
    db.mark_milestone(learner.id, "mehndi", "started_skill")  # a different skill

    # Idempotent: re-marking an achieved milestone doesn't move its timestamp.
    assert again.achieved_at == first.achieved_at

    tailoring_only = db.get_milestones(learner.id, skill_id="tailoring")
    assert [m.milestone_id for m in tailoring_only] == ["started_skill"]

    everything = db.get_milestones(learner.id)
    assert {(m.skill_id, m.milestone_id) for m in everything} == {
        ("tailoring", "started_skill"),
        ("mehndi", "started_skill"),
    }


def test_get_progress_resolves_real_titles_and_labels_in_her_language():
    """Bug found by inspection while reviewing this module: lesson titles
    and concept labels were the raw internal ids verbatim (e.g.
    "c-tape-basics"), never resolved from the content store -- exactly the
    "progress screen full of ids instead of words" the roadmap complains
    about. Production code always uses the real skill_id as the lesson_id
    (wrapup.py), so this should resolve for real data."""
    learner = db.create_learner(
        name="Priya",
        village=None,
        language="hi-IN",
        pin="5555",
        interest_skill="tailoring",
        starting_level="some",
        notes=None,
        consent_given_at=_consent_now(),
    )
    db.upsert_lesson_progress(learner.id, "tailoring", "in_progress")
    db.upsert_concept_mastery(learner.id, "c-tape-basics", "strong")

    progress = db.get_progress(learner.id)

    assert progress["skill"] == "सिलाई"
    lesson = next(entry for entry in progress["lessons"] if entry["lesson_id"] == "tailoring")
    assert lesson["title"] == "सिलाई"
    concept = next(
        entry for entry in progress["concepts"] if entry["concept_id"] == "c-tape-basics"
    )
    assert concept["label"] == "इंच टेप का उपयोग"


def test_get_progress_falls_back_to_raw_id_for_unknown_lesson_or_concept():
    learner = db.create_learner(
        name="Priya",
        village=None,
        language="hi-IN",
        pin="6666",
        interest_skill=None,
        starting_level="some",
        notes=None,
        consent_given_at=_consent_now(),
    )
    db.upsert_lesson_progress(learner.id, "not-a-real-skill", "in_progress")
    db.upsert_concept_mastery(learner.id, "not-a-real-concept", "strong")

    progress = db.get_progress(learner.id)

    assert progress["lessons"][0]["title"] == "not-a-real-skill"
    assert progress["concepts"][0]["label"] == "not-a-real-concept"
