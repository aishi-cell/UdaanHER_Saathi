from typing import Literal

from pydantic import BaseModel

from app.models.ui import UICommand


class LatencyMs(BaseModel):
    stt: int
    agent: int
    tts: int


class TurnResponse(BaseModel):
    transcript: str | None
    reply_text: str
    reply_audio_b64: str
    ui: UICommand
    stage: str
    latency_ms: LatencyMs


class SessionRequest(BaseModel):
    learner_name: str | None = None
    pin: str | None = None
    # Omitted -> the voice-first path: the session opens in choose_language
    # and Saathi asks for her language by voice (with tappable cards).
    language: Literal["gu-IN", "hi-IN", "en-IN"] | None = None


class SessionResponse(BaseModel):
    session_id: str
    learner_id: str | None
    greeting_audio_b64: str
    greeting_text: str
    ui: UICommand
    stage: str
