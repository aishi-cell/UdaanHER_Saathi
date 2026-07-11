from base64 import b64decode, b64encode
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

FIXTURE_WAV = Path(__file__).parent / "fixtures" / "sample.wav"


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


def test_turn_echoes_transcript_with_mocked_sarvam():
    with patch("httpx.AsyncClient.post", new=AsyncMock(side_effect=_fake_post)):
        response = client.post(
            "/api/turn",
            data={"session_id": "any-session"},
            files={"audio": ("clip.webm", b"fake-audio-bytes", "audio/webm")},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["transcript"] == "Namaste"
    assert body["reply_text"] == "Aapne kaha: Namaste"
    assert b64decode(body["reply_audio_b64"]) == b"fake-mp3-bytes"
    assert body["ui"] == {"type": "idle"}
    assert body["stage"] == "greet"
    assert set(body["latency_ms"]) == {"stt", "agent", "tts"}
    assert all(v >= 0 for v in body["latency_ms"].values())


def test_turn_requires_audio_or_tapped_option():
    response = client.post("/api/turn", data={"session_id": "any-session"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "missing_input"


def test_turn_rejects_both_audio_and_tapped_option():
    response = client.post(
        "/api/turn",
        data={"session_id": "any-session", "tapped_option_id": "beauty"},
        files={"audio": ("clip.webm", b"fake-audio-bytes", "audio/webm")},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "ambiguous_input"


def test_turn_tapped_option_skips_stt_and_echoes():
    with patch("httpx.AsyncClient.post", new=AsyncMock(side_effect=_fake_post)):
        response = client.post(
            "/api/turn",
            data={"session_id": "any-session", "tapped_option_id": "tailoring"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["transcript"] is None
    assert body["reply_text"] == "Aapne chuna: tailoring"
    assert b64decode(body["reply_audio_b64"]) == b"fake-mp3-bytes"
    assert body["latency_ms"]["stt"] == 0


@pytest.mark.live
@pytest.mark.skipif(not FIXTURE_WAV.exists(), reason="no fixture WAV recorded yet (see T02)")
def test_turn_live_end_to_end():
    audio_bytes = FIXTURE_WAV.read_bytes()
    response = client.post(
        "/api/turn",
        data={"session_id": "live-session"},
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
