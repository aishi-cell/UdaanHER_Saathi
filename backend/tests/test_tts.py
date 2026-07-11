from base64 import b64encode
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.services.tts import TTS_CHAR_LIMIT, TtsError, _split_into_chunks, synthesize

FAKE_MP3_BYTES = b"ID3fake-mp3-bytes"


def _fake_response(mp3_bytes: bytes = FAKE_MP3_BYTES) -> httpx.Response:
    return httpx.Response(
        status_code=200,
        json={"request_id": "req-1", "audios": [b64encode(mp3_bytes).decode()]},
    )


@pytest.mark.asyncio
async def test_synthesize_success():
    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=_fake_response())):
        result = await synthesize("Namaste", "hi-IN")

    assert result.mp3_bytes == FAKE_MP3_BYTES
    assert result.elapsed_ms >= 0


@pytest.mark.asyncio
async def test_synthesize_non_200_raises_tts_error():
    fake_response = httpx.Response(status_code=400, json={"error": {"message": "bad speaker"}})
    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=fake_response)):
        with pytest.raises(TtsError) as exc_info:
            await synthesize("Namaste", "hi-IN")

    assert exc_info.value.status_code == 400
    assert "bad speaker" in exc_info.value.message


@pytest.mark.asyncio
async def test_synthesize_timeout_raises_tts_error():
    with patch(
        "httpx.AsyncClient.post",
        new=AsyncMock(side_effect=httpx.TimeoutException("timed out")),
    ):
        with pytest.raises(TtsError):
            await synthesize("Namaste", "hi-IN")


@pytest.mark.asyncio
async def test_synthesize_connect_error_raises_tts_error():
    with patch(
        "httpx.AsyncClient.post",
        new=AsyncMock(side_effect=httpx.ConnectError("dns lookup failed")),
    ):
        with pytest.raises(TtsError):
            await synthesize("Namaste", "hi-IN")


@pytest.mark.asyncio
async def test_synthesize_splits_long_text_and_concatenates(caplog):
    long_text = "Ek. " * (TTS_CHAR_LIMIT // 4 + 50)
    mock_post = AsyncMock(return_value=_fake_response(b"chunk"))
    with patch("httpx.AsyncClient.post", new=mock_post):
        with caplog.at_level("WARNING", logger="udaanher.tts"):
            result = await synthesize(long_text, "hi-IN")

    assert mock_post.call_count > 1
    assert result.mp3_bytes == b"chunk" * mock_post.call_count
    assert any("split into" in record.message for record in caplog.records)


def test_split_into_chunks_respects_sentence_boundaries():
    text = "One. Two. Three."
    chunks = _split_into_chunks(text, limit=8)
    assert all(len(chunk) <= 9 for chunk in chunks)
    assert "".join(chunks).replace(" ", "") == text.replace(" ", "")


@pytest.mark.live
@pytest.mark.asyncio
async def test_synthesize_live_writes_playable_mp3():
    gu_result = await synthesize("Namaste, main aapki saathi hoon", "gu-IN")
    hi_result = await synthesize("Namaste, main aapki saathi hoon", "hi-IN")

    output_dir = Path(__file__).parent / "live_output"
    output_dir.mkdir(exist_ok=True)
    gu_path = output_dir / "live_gu.mp3"
    hi_path = output_dir / "live_hi.mp3"
    gu_path.write_bytes(gu_result.mp3_bytes)
    hi_path.write_bytes(hi_result.mp3_bytes)

    print(f"Wrote {gu_path} ({len(gu_result.mp3_bytes)} bytes)")
    print(f"Wrote {hi_path} ({len(hi_result.mp3_bytes)} bytes)")

    assert len(gu_result.mp3_bytes) > 0
    assert len(hi_result.mp3_bytes) > 0
