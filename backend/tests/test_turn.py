from base64 import b64decode, b64encode
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.agent.nodes.greet import GreetExtraction  # noqa: F401 (schema for greet mocks)
from app.main import app
from app.models import db

FIXTURE_WAV = Path(__file__).parent / "fixtures" / "sample.wav"


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


async def _fake_post(url, **kwargs):
    if "speech-to-text" in str(url):
        return httpx.Response(
            200, json={"transcript": "Namaste", "language_code": "hi-IN", "request_id": "r1"}
        )
    if "text-to-speech" in str(url):
        return httpx.Response(
            200,
            json={"request_id": "r2", "audios": [b64encode(b"fake-mp3-bytes").decode()]},
        )
    raise AssertionError(f"unexpected url {url}")


def test_turn_advances_stage_with_mocked_sarvam(client):
    with (
        patch("httpx.AsyncClient.post", new=AsyncMock(side_effect=_fake_post)),
        patch(
            "app.agent.nodes.greet.ask_conversational", new=AsyncMock(return_value="Namaste!")
        ),
        patch(
            "app.agent.nodes.greet.extract_structured",
            new=AsyncMock(return_value=GreetExtraction(name="Sunita", returning=False)),
        ),
    ):
        session_id = client.post("/api/session", json={"language": "hi-IN"}).json()["session_id"]

        response = client.post(
            "/api/turn",
            data={"session_id": session_id},
            files={"audio": ("clip.webm", b"fake-audio-bytes", "audio/webm")},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["transcript"] == "Namaste"
    # /api/session runs greet's step0 (asks); this turn runs greet's step1
    # (extracts name + new visitor -> asks consent), staying in greet.
    assert body["stage"] == "greet"
    assert b64decode(body["reply_audio_b64"]) == b"fake-mp3-bytes"
    assert body["ui"] == {"type": "idle"}
    assert set(body["latency_ms"]) == {"stt", "agent", "tts"}
    assert all(v >= 0 for v in body["latency_ms"].values())


def test_turn_passes_session_language_to_stt(client):
    """An explicit language hint measurably improves Sarvam's accuracy on
    accented/regional/code-mixed speech versus blind auto-detect."""
    captured_data = {}

    async def _capturing_post(url, **kwargs):
        if "speech-to-text" in str(url):
            captured_data.update(kwargs.get("data") or {})
        return await _fake_post(url, **kwargs)

    with (
        patch("httpx.AsyncClient.post", new=AsyncMock(side_effect=_capturing_post)),
        patch(
            "app.agent.nodes.greet.ask_conversational", new=AsyncMock(return_value="Namaste!")
        ),
        patch(
            "app.agent.nodes.greet.extract_structured",
            new=AsyncMock(return_value=GreetExtraction(name="Sunita", returning=False)),
        ),
    ):
        session_id = client.post("/api/session", json={"language": "gu-IN"}).json()["session_id"]

        client.post(
            "/api/turn",
            data={"session_id": session_id},
            files={"audio": ("clip.webm", b"fake-audio-bytes", "audio/webm")},
        )

    assert captured_data.get("language_code") == "gu-IN"


def test_turn_requires_audio_or_tapped_option(client):
    response = client.post("/api/turn", data={"session_id": "any-session"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "missing_input"


def test_turn_rejects_both_audio_and_tapped_option(client):
    response = client.post(
        "/api/turn",
        data={"session_id": "any-session", "tapped_option_id": "beauty"},
        files={"audio": ("clip.webm", b"fake-audio-bytes", "audio/webm")},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "ambiguous_input"


def test_turn_tapped_option_skips_stt(client):
    with (
        patch("httpx.AsyncClient.post", new=AsyncMock(side_effect=_fake_post)),
        patch(
            "app.agent.nodes.greet.ask_conversational", new=AsyncMock(return_value="Namaste!")
        ),
        patch(
            "app.agent.nodes.greet.extract_structured",
            new=AsyncMock(return_value=GreetExtraction(name="Sunita", returning=False)),
        ),
    ):
        session_id = client.post("/api/session", json={"language": "hi-IN"}).json()["session_id"]

        response = client.post(
            "/api/turn",
            data={"session_id": session_id, "tapped_option_id": "tailoring"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["transcript"] is None
    # A tap while still in greet is nonsensical UI-wise, but the pipeline
    # should still process it as her greet reply (transcript = "tailoring")
    # and advance the same way voice input would.
    assert body["stage"] == "greet"
    assert b64decode(body["reply_audio_b64"]) == b"fake-mp3-bytes"
    assert body["latency_ms"]["stt"] == 0


@pytest.mark.live
@pytest.mark.skipif(not FIXTURE_WAV.exists(), reason="no fixture WAV recorded yet (see T02)")
def test_turn_live_end_to_end(client):
    session_id = client.post("/api/session", json={"language": "hi-IN"}).json()["session_id"]

    audio_bytes = FIXTURE_WAV.read_bytes()
    response = client.post(
        "/api/turn",
        data={"session_id": session_id},
        files={"audio": ("sample.wav", audio_bytes, "audio/wav")},
    )

    assert response.status_code == 200
    body = response.json()
    mp3_bytes = b64decode(body["reply_audio_b64"])
    assert len(mp3_bytes) > 0

    latency = body["latency_ms"]
    print(f"latency_ms: {latency}")
    assert latency["stt"] > 0
    assert latency["tts"] > 0
