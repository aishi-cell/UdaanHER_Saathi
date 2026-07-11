import base64
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from pydantic import TypeAdapter

from app.agent.graph import compile_graph
from app.agent.state import ProfileDraft, initial_state
from app.config import get_settings
from app.errors import ApiError, api_error_handler, unhandled_error_handler
from app.middleware import RequestLogMiddleware
from app.models import db as db_repo
from app.models.api import LatencyMs, SessionRequest, SessionResponse, TurnResponse
from app.models.ui import ProgressPayload, UICommand
from app.services.stt import SttError, transcribe
from app.services.timing import timed
from app.services.tts import TtsError, synthesize

logging.basicConfig(level=logging.INFO)

settings = get_settings()
db_repo.init_db()

APP_VERSION = "0.1.0"
CHECKPOINT_DB_PATH = "data/checkpoints.db"

ui_adapter: TypeAdapter = TypeAdapter(UICommand)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Path(CHECKPOINT_DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    async with AsyncSqliteSaver.from_conn_string(CHECKPOINT_DB_PATH) as saver:
        app.state.agent_graph = compile_graph(saver)
        yield


app = FastAPI(title="UdaanHer Saathi", lifespan=lifespan)

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


def _profile_draft_from_learner(learner) -> ProfileDraft:
    return ProfileDraft(
        name=learner.name,
        village=learner.village or "",
        interest=learner.interest_skill or "",
        starting_level=learner.starting_level or "some",
        notes=learner.notes or "",
    )


@app.post("/api/session", response_model=SessionResponse)
async def post_session(request: Request, payload: SessionRequest) -> SessionResponse:
    learner = None
    if payload.learner_name and payload.pin:
        learner = db_repo.get_learner_by_name_pin(payload.learner_name, payload.pin)

    session = db_repo.create_session(
        learner_id=learner.id if learner else None,
        language=payload.language,
    )

    starting_state = initial_state(
        session_id=session.id,
        learner_id=learner.id if learner else None,
        language=payload.language,
        stage="resume" if learner else "greet",
        profile=_profile_draft_from_learner(learner) if learner else None,
    )

    graph = request.app.state.agent_graph
    config = {"configurable": {"thread_id": session.id}}
    result_state, _ = await timed(graph.ainvoke(starting_state, config=config))

    greeting_text = result_state["reply_text"]
    try:
        tts_result, _ = await timed(synthesize(greeting_text, payload.language))
    except TtsError as exc:
        raise ApiError(502, "tts_failed", exc.message) from exc

    return SessionResponse(
        session_id=session.id,
        learner_id=learner.id if learner else None,
        greeting_audio_b64=base64.b64encode(tts_result.mp3_bytes).decode(),
        greeting_text=greeting_text,
        ui=ui_adapter.validate_python(result_state["ui"]),
        stage=result_state["stage"],
    )


@app.get("/api/learner/{learner_id}/progress", response_model=ProgressPayload)
def get_learner_progress(learner_id: str) -> ProgressPayload:
    return ProgressPayload(**db_repo.get_progress(learner_id))


@app.post("/api/turn", response_model=TurnResponse)
async def post_turn(
    request: Request,
    session_id: str = Form(...),
    audio: UploadFile | None = File(None),
    tapped_option_id: str | None = Form(None),
) -> TurnResponse:
    if audio is None and tapped_option_id is None:
        raise ApiError(400, "missing_input", "Provide either audio or tapped_option_id.")
    if audio is not None and tapped_option_id is not None:
        raise ApiError(400, "ambiguous_input", "Provide only one of audio or tapped_option_id.")

    if audio is not None:
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
    else:
        transcript = None
        stt_ms = 0

    agent_input = transcript if transcript else (tapped_option_id or "")

    graph = request.app.state.agent_graph
    config = {"configurable": {"thread_id": session_id}}
    result_state, agent_ms = await timed(
        graph.ainvoke({"transcript": agent_input}, config=config)
    )

    reply_text = result_state["reply_text"]
    try:
        tts_result, tts_ms = await timed(synthesize(reply_text, result_state["language"]))
    except TtsError as exc:
        raise ApiError(502, "tts_failed", exc.message) from exc

    return TurnResponse(
        transcript=transcript,
        reply_text=reply_text,
        reply_audio_b64=base64.b64encode(tts_result.mp3_bytes).decode(),
        ui=ui_adapter.validate_python(result_state["ui"]),
        stage=result_state["stage"],
        latency_ms=LatencyMs(stt=stt_ms, agent=agent_ms, tts=tts_ms),
    )
