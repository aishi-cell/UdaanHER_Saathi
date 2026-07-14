import logging
import re
import time
from base64 import b64decode
from dataclasses import dataclass

import httpx

from app.config import get_settings

SARVAM_TTS_URL = "https://api.sarvam.ai/text-to-speech"
TTS_TIMEOUT_SECONDS = 15.0
TTS_CHAR_LIMIT = 2500

logger = logging.getLogger("udaanher.tts")


class TtsError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass
class Mp3Result:
    mp3_bytes: bytes
    elapsed_ms: float


def _extract_error_message(response: httpx.Response) -> str:
    try:
        body = response.json()
        return body.get("error", {}).get("message") or response.text
    except ValueError:
        return response.text


# Emoji and pictograph ranges only -- must NOT touch Devanagari (U+0900-097F)
# or Gujarati (U+0A80-0AFF) text. Covers emoji blocks, dingbats/misc symbols
# (includes hearts), regional indicators, variation selectors, ZWJ, and
# skin-tone modifiers.
_EMOJI_RE = re.compile(
    "["
    "\U0001f000-\U0001faff"  # mahjong .. symbols & pictographs extended
    "☀-➿"  # misc symbols + dingbats (sun, hearts, sparkles, checkmarks)
    "⬀-⯿"  # misc symbols and arrows (stars, geometric)
    "︎️"  # variation selectors
    "‍"  # zero-width joiner
    "\U0001f3fb-\U0001f3ff"  # skin tone modifiers
    "]+"
)


def strip_emoji(text: str) -> str:
    """Remove emoji before synthesis -- Sarvam TTS reads them aloud or mangles them."""
    stripped = _EMOJI_RE.sub("", text)
    stripped = re.sub(r"  +", " ", stripped).strip()
    # An all-emoji reply should never happen, but sending Sarvam an empty
    # string is a guaranteed 400 -- keep the original in that case.
    return stripped if stripped else text


def _split_into_chunks(text: str, limit: int) -> list[str]:
    if len(text) <= limit:
        return [text]

    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        candidate = f"{current} {sentence}".strip() if current else sentence
        if len(candidate) > limit:
            if current:
                chunks.append(current)
            current = sentence
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


async def _synthesize_chunk(
    client: httpx.AsyncClient, text: str, language: str, api_key: str, speaker: str
) -> bytes:
    response = await client.post(
        SARVAM_TTS_URL,
        headers={"api-subscription-key": api_key},
        json={
            "text": text,
            "target_language_code": language,
            "model": "bulbul:v3",
            "speaker": speaker,
            "output_audio_codec": "mp3",
            "speech_sample_rate": 24000,
        },
    )
    if response.status_code != 200:
        raise TtsError(_extract_error_message(response), status_code=response.status_code)
    body = response.json()
    return b64decode(body["audios"][0])


async def synthesize(text: str, language: str) -> Mp3Result:
    settings = get_settings()
    text = strip_emoji(text)
    chunks = _split_into_chunks(text, TTS_CHAR_LIMIT)
    if len(chunks) > 1:
        logger.warning(
            "TTS text was %d chars (limit %d); split into %d chunks. Mentor replies "
            "should be 2-3 sentences per Spec S9.3 -- a prompt is likely misbehaving.",
            len(text),
            TTS_CHAR_LIMIT,
            len(chunks),
        )

    start = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=TTS_TIMEOUT_SECONDS) as client:
            mp3_parts = [
                await _synthesize_chunk(
                    client, chunk, language, settings.sarvam_api_key, settings.tts_speaker
                )
                for chunk in chunks
            ]
    except httpx.TimeoutException as exc:
        raise TtsError(f"Sarvam TTS request timed out after {TTS_TIMEOUT_SECONDS}s") from exc
    except httpx.RequestError as exc:
        raise TtsError(f"Sarvam TTS request failed: {exc}") from exc

    elapsed_ms = (time.perf_counter() - start) * 1000
    return Mp3Result(mp3_bytes=b"".join(mp3_parts), elapsed_ms=elapsed_ms)
