from pydantic import BaseModel


class LatencyMs(BaseModel):
    stt: int
    agent: int
    tts: int


class TurnResponse(BaseModel):
    transcript: str | None
    reply_text: str
    reply_audio_b64: str
    ui: dict
    stage: str
    latency_ms: LatencyMs
