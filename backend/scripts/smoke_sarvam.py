"""Proves the Sarvam STT and TTS keys work (Spec S6.1, S6.2).

Run from backend/: uv run python scripts/smoke_sarvam.py
"""

import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings

FIXTURE_WAV = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "sample.wav"
OUT_MP3 = Path(__file__).resolve().parent.parent / "out.mp3"
TTS_TEXT = "Namaste, main aapki saathi hoon"


def smoke_stt(settings) -> None:
    if not FIXTURE_WAV.exists():
        print(f"SKIP stt: fixture WAV not found at {FIXTURE_WAV}")
        return

    with open(FIXTURE_WAV, "rb") as f:
        response = httpx.post(
            "https://api.sarvam.ai/speech-to-text",
            headers={"api-subscription-key": settings.sarvam_api_key},
            files={"file": ("sample.wav", f, "audio/wav")},
            data={"model": "saaras:v3", "mode": "transcribe"},
            timeout=15,
        )
    response.raise_for_status()
    body = response.json()
    print("STT transcript:", body.get("transcript"))
    print("STT language_code:", body.get("language_code"))
    print("STT request_id:", body.get("request_id"))


def smoke_tts(settings) -> None:
    response = httpx.post(
        "https://api.sarvam.ai/text-to-speech",
        headers={"api-subscription-key": settings.sarvam_api_key},
        json={
            "text": TTS_TEXT,
            "target_language_code": "hi-IN",
            "model": "bulbul:v3",
            "speaker": settings.tts_speaker,
            "output_audio_codec": "mp3",
            "speech_sample_rate": 24000,
        },
        timeout=15,
    )
    response.raise_for_status()
    body = response.json()

    import base64

    audio_bytes = base64.b64decode(body["audios"][0])
    OUT_MP3.write_bytes(audio_bytes)
    print(f"TTS wrote {len(audio_bytes)} bytes to {OUT_MP3}")


def main() -> None:
    settings = get_settings()
    smoke_stt(settings)
    smoke_tts(settings)


if __name__ == "__main__":
    main()
