from base64 import b64decode, b64encode
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import db


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def temp_db(tmp_path):
    db.configure_engine(f"sqlite:///{tmp_path / 'test.db'}")
    db.init_db()
    yield
    db._engine = None


async def _fake_tts_post(url, **kwargs):
    assert "text-to-speech" in str(url)
    return httpx.Response(
        200, json={"request_id": "r1", "audios": [b64encode(b"fake-mp3-bytes").decode()]}
    )


def test_session_new_visitor_is_greeted(client):
    with (
        patch("httpx.AsyncClient.post", new=AsyncMock(side_effect=_fake_tts_post)),
        patch(
            "app.agent.nodes.greet.ask_conversational",
            new=AsyncMock(return_value="Namaste! Aapka naam kya hai?"),
        ),
    ):
        response = client.post("/api/session", json={"language": "gu-IN"})

    assert response.status_code == 200
    body = response.json()
    assert body["learner_id"] is None
    # /api/session runs greet's first sub-turn only (asks name+consent); the
    # real onboarding conversation (T12) needs several more turns to reach
    # discover -- see test_onboarding.py and test_agent_graph.py.
    assert body["stage"] == "greet"
    assert body["session_id"]
    assert body["greeting_text"] == "Namaste! Aapka naam kya hai?"
    assert b64decode(body["greeting_audio_b64"]) == b"fake-mp3-bytes"
    assert body["ui"] == {"type": "idle"}


def test_session_returning_learner_resolves_by_name_and_pin(client):
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

    with patch("httpx.AsyncClient.post", new=AsyncMock(side_effect=_fake_tts_post)):
        response = client.post(
            "/api/session",
            json={"learner_name": "Sunita", "pin": "1234", "language": "gu-IN"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["learner_id"] == learner.id
    # resume node (Spec S9.1) transitions straight to teach, since her profile
    # already exists in the DB.
    assert body["stage"] == "teach"
    assert "Sunita" in body["greeting_text"]


def test_session_wrong_pin_treated_as_new_visitor(client):
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

    with (
        patch("httpx.AsyncClient.post", new=AsyncMock(side_effect=_fake_tts_post)),
        patch("app.agent.nodes.greet.ask_conversational", new=AsyncMock(return_value="Namaste!")),
    ):
        response = client.post(
            "/api/session",
            json={"learner_name": "Sunita", "pin": "0000", "language": "gu-IN"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["learner_id"] is None
    assert body["stage"] == "greet"


def test_progress_endpoint_matches_repository_shape(client):
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


def test_progress_endpoint_unknown_learner_returns_empty_lists(client):
    response = client.get("/api/learner/does-not-exist/progress")

    assert response.status_code == 200
    body = response.json()
    assert body["lessons"] == []
    assert body["concepts"] == []
