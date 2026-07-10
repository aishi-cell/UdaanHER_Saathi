import time
from dataclasses import dataclass

import httpx

from app.config import get_settings

SARVAM_STT_URL = "https://api.sarvam.ai/speech-to-text"
STT_TIMEOUT_SECONDS = 15.0


class SttError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass
class TranscriptResult:
    transcript: str
    language_code: str | None
    request_id: str | None
    elapsed_ms: float


def _extract_error_message(response: httpx.Response) -> str:
    try:
        body = response.json()
        return body.get("error", {}).get("message") or response.text
    except ValueError:
        return response.text


async def transcribe(
    audio_bytes: bytes,
    language: str | None = None,
    filename: str = "audio.webm",
    content_type: str = "audio/webm",
) -> TranscriptResult:
    settings = get_settings()
    data = {"model": "saaras:v3", "mode": "transcribe"}
    if language:
        data["language_code"] = language

    start = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=STT_TIMEOUT_SECONDS) as client:
            response = await client.post(
                SARVAM_STT_URL,
                headers={"api-subscription-key": settings.sarvam_api_key},
                files={"file": (filename, audio_bytes, content_type)},
                data=data,
            )
    except httpx.TimeoutException as exc:
        raise SttError(f"Sarvam STT request timed out after {STT_TIMEOUT_SECONDS}s") from exc

    elapsed_ms = (time.perf_counter() - start) * 1000

    if response.status_code != 200:
        raise SttError(_extract_error_message(response), status_code=response.status_code)

    body = response.json()
    return TranscriptResult(
        transcript=body.get("transcript", ""),
        language_code=body.get("language_code"),
        request_id=body.get("request_id"),
        elapsed_ms=elapsed_ms,
    )
