from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import db

client = TestClient(app)


@pytest.fixture(autouse=True)
def temp_db(tmp_path):
    db.configure_engine(f"sqlite:///{tmp_path / 'test.db'}")
    db.init_db()
    yield
    db._engine = None


def test_session_new_visitor_has_no_learner_and_greet_stage():
    response = client.post("/api/session", json={"language": "gu-IN"})

    assert response.status_code == 200
    body = response.json()
    assert body["learner_id"] is None
    assert body["stage"] == "greet"
    assert body["session_id"]


def test_session_returning_learner_resolves_by_name_and_pin():
    learner = db.create_learner(
        name="Sunita",
        village="Rampur",
        language="gu-IN",
        pin="1234",
        interest_skill="tailoring",
        starting_level="some",
        notes=None,
        consent_given_at=datetime.now(timezone.utc),
    )

    response = client.post(
        "/api/session",
        json={"learner_name": "Sunita", "pin": "1234", "language": "gu-IN"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["learner_id"] == learner.id
    assert body["stage"] == "resume"


def test_session_wrong_pin_treated_as_new_visitor():
    db.create_learner(
        name="Sunita",
        village=None,
        language="gu-IN",
        pin="1234",
        interest_skill=None,
        starting_level=None,
        notes=None,
        consent_given_at=datetime.now(timezone.utc),
    )

    response = client.post(
        "/api/session",
        json={"learner_name": "Sunita", "pin": "0000", "language": "gu-IN"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["learner_id"] is None
    assert body["stage"] == "greet"


def test_progress_endpoint_matches_repository_shape():
    learner = db.create_learner(
        name="Priya",
        village=None,
        language="gu-IN",
        pin="1111",
        interest_skill="tailoring",
        starting_level="some",
        notes=None,
        consent_given_at=datetime.now(timezone.utc),
    )
    db.upsert_lesson_progress(learner.id, "tail-01-measure", "in_progress")
    db.upsert_concept_mastery(learner.id, "c-body-measure", "strong")

    response = client.get(f"/api/learner/{learner.id}/progress")

    assert response.status_code == 200
    body = response.json()
    assert body["lessons"] == [
        {"lesson_id": "tail-01-measure", "title": "tail-01-measure", "status": "current"}
    ]
    assert body["concepts"] == [
        {"concept_id": "c-body-measure", "label": "c-body-measure", "mastery": "strong"}
    ]


def test_progress_endpoint_unknown_learner_returns_empty_lists():
    response = client.get("/api/learner/does-not-exist/progress")

    assert response.status_code == 200
    body = response.json()
    assert body["lessons"] == []
    assert body["concepts"] == []
