from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.services.stt import SttError, transcribe

FIXTURE_WAV = Path(__file__).parent / "fixtures" / "sample.wav"


@pytest.mark.asyncio
async def test_transcribe_success():
    fake_response = httpx.Response(
        status_code=200,
        json={"transcript": "Namaste", "language_code": "hi-IN", "request_id": "req-1"},
    )
    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=fake_response)):
        result = await transcribe(b"fake-audio-bytes")

    assert result.transcript == "Namaste"
    assert result.language_code == "hi-IN"
    assert result.request_id == "req-1"
    assert result.elapsed_ms >= 0


@pytest.mark.asyncio
async def test_transcribe_empty_transcript_does_not_raise():
    fake_response = httpx.Response(
        status_code=200,
        json={"transcript": "", "language_code": "hi-IN", "request_id": "req-2"},
    )
    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=fake_response)):
        result = await transcribe(b"fake-audio-bytes")

    assert result.transcript == ""


@pytest.mark.asyncio
async def test_transcribe_non_200_raises_stt_error():
    fake_response = httpx.Response(
        status_code=400,
        json={"error": {"message": "invalid audio format"}},
    )
    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=fake_response)):
        with pytest.raises(SttError) as exc_info:
            await transcribe(b"fake-audio-bytes")

    assert exc_info.value.status_code == 400
    assert "invalid audio format" in exc_info.value.message


@pytest.mark.asyncio
async def test_transcribe_timeout_raises_stt_error():
    with patch(
        "httpx.AsyncClient.post",
        new=AsyncMock(side_effect=httpx.TimeoutException("timed out")),
    ):
        with pytest.raises(SttError):
            await transcribe(b"fake-audio-bytes")


@pytest.mark.asyncio
async def test_transcribe_connect_error_raises_stt_error():
    with patch(
        "httpx.AsyncClient.post",
        new=AsyncMock(side_effect=httpx.ConnectError("dns lookup failed")),
    ):
        with pytest.raises(SttError):
            await transcribe(b"fake-audio-bytes")


@pytest.mark.asyncio
async def test_transcribe_strips_codecs_parameter_from_content_type():
    """Browser MediaRecorder blobs report a type like
    "audio/webm;codecs=opus"; Sarvam's content-type allow-list rejects
    anything with a codecs parameter, so we must strip it before sending."""
    fake_response = httpx.Response(
        status_code=200,
        json={"transcript": "ok", "language_code": "hi-IN", "request_id": "req-3"},
    )
    mock_post = AsyncMock(return_value=fake_response)
    with patch("httpx.AsyncClient.post", new=mock_post):
        await transcribe(
            b"fake-audio-bytes", filename="clip.webm", content_type="audio/webm;codecs=opus"
        )

    sent_content_type = mock_post.call_args.kwargs["files"]["file"][2]
    assert sent_content_type == "audio/webm"


@pytest.mark.live
@pytest.mark.skipif(not FIXTURE_WAV.exists(), reason="no fixture WAV recorded yet (see T02)")
@pytest.mark.asyncio
async def test_transcribe_live_fixture():
    audio_bytes = FIXTURE_WAV.read_bytes()
    result = await transcribe(audio_bytes, filename="sample.wav", content_type="audio/wav")

    print(f"Live transcript: {result.transcript!r} ({result.language_code})")
    assert result.transcript
    assert result.elapsed_ms > 0
