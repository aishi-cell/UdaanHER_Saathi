from typing import Literal

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


class SessionRequest(BaseModel):
    learner_name: str | None = None
    pin: str | None = None
    language: Literal["gu-IN", "hi-IN", "en-IN"]


class SessionResponse(BaseModel):
    session_id: str
    learner_id: str | None
    stage: str


class ProgressLessonEntry(BaseModel):
    lesson_id: str
    title: str
    status: str


class ProgressConceptEntry(BaseModel):
    concept_id: str
    label: str
    mastery: str


class ProgressResponse(BaseModel):
    skill: str
    lessons: list[ProgressLessonEntry]
    concepts: list[ProgressConceptEntry]
    next_step_text: str
