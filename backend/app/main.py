import base64
import logging

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.errors import ApiError, api_error_handler, unhandled_error_handler
from app.middleware import RequestLogMiddleware
from app.models import db as db_repo
from app.models.api import (
    LatencyMs,
    ProgressResponse,
    SessionRequest,
    SessionResponse,
    TurnResponse,
)
from app.services.stt import SttError, transcribe
from app.services.timing import timed
from app.services.tts import TtsError, synthesize

logging.basicConfig(level=logging.INFO)

settings = get_settings()
db_repo.init_db()

APP_VERSION = "0.1.0"
ECHO_REPLY_LANGUAGE = "hi-IN"

app = FastAPI(title="UdaanHer Saathi")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLogMiddleware)

app.add_exception_handler(ApiError, api_error_handler)
app.add_exception_handler(Exception, unhandled_error_handler)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "version": APP_VERSION}


@app.post("/api/session", response_model=SessionResponse)
def post_session(payload: SessionRequest) -> SessionResponse:
    learner = None
    if payload.learner_name and payload.pin:
        learner = db_repo.get_learner_by_name_pin(payload.learner_name, payload.pin)

    session = db_repo.create_session(
        learner_id=learner.id if learner else None,
        language=payload.language,
    )

    return SessionResponse(
        session_id=session.id,
        learner_id=learner.id if learner else None,
        stage="resume" if learner else "greet",
    )


@app.get("/api/learner/{learner_id}/progress", response_model=ProgressResponse)
def get_learner_progress(learner_id: str) -> ProgressResponse:
    return ProgressResponse(**db_repo.get_progress(learner_id))


async def _echo_reply(transcript: str | None) -> str:
    spoken = transcript if transcript else "(kuch sunai nahi diya)"
    return f"Aapne kaha: {spoken}"


@app.post("/api/turn", response_model=TurnResponse)
async def post_turn(
    session_id: str = Form(...),
    audio: UploadFile = File(...),
) -> TurnResponse:
    audio_bytes = await audio.read()
    try:
        stt_result, stt_ms = await timed(
            transcribe(
                audio_bytes,
                filename=audio.filename or "audio.webm",
                content_type=audio.content_type or "audio/webm",
            )
        )
    except SttError as exc:
        raise ApiError(502, "stt_failed", exc.message) from exc
    transcript = stt_result.transcript

    reply_text, agent_ms = await timed(_echo_reply(transcript))

    try:
        tts_result, tts_ms = await timed(synthesize(reply_text, ECHO_REPLY_LANGUAGE))
    except TtsError as exc:
        raise ApiError(502, "tts_failed", exc.message) from exc

    return TurnResponse(
        transcript=transcript,
        reply_text=reply_text,
        reply_audio_b64=base64.b64encode(tts_result.mp3_bytes).decode(),
        ui={"type": "idle"},
        stage="greet",
        latency_ms=LatencyMs(stt=stt_ms, agent=agent_ms, tts=tts_ms),
    )
