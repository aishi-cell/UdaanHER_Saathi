import base64
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from pydantic import TypeAdapter

from app.agent.graph import compile_graph
from app.agent.nodes import choose_language
from app.agent.nodes.resume import profile_from_learner
from app.agent.state import initial_state
from app.config import get_settings
from app.content import store as content_store
from app.errors import ApiError, api_error_handler, unhandled_error_handler
from app.middleware import RequestLogMiddleware
from app.models import db as db_repo
from app.models.api import LatencyMs, SessionRequest, SessionResponse, TurnResponse
from app.models.ui import ProgressPayload, UICommand
from app.services.llm import describe_practice_photo
from app.services.stt import SttError, transcribe
from app.services.timing import timed
from app.services.tts import TtsError, synthesize

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("udaanher.turn")

settings = get_settings()
db_repo.init_db()
# Fail loud at boot, not in front of a learner: a typo in any cached skill
# package refuses to start with a message naming the file + field (plan v2).
_skills = content_store.validate_all()
logging.getLogger("udaanher.content").info("content store OK: %s", _skills or "(empty)")

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


@app.post("/api/session", response_model=SessionResponse)
async def post_session(request: Request, payload: SessionRequest) -> SessionResponse:
    learner = None
    if payload.learner_name and payload.pin:
        learner = db_repo.get_learner_by_name_pin(payload.learner_name, payload.pin)

    # No language given -> voice-first: Saathi opens by asking for it.
    # The placeholder language covers the trilingual prompt's TTS and is
    # overwritten by choose_language the moment she answers.
    language = payload.language or choose_language.PROMPT_TTS_LANGUAGE
    if learner:
        stage = "resume"
    elif payload.language:
        stage = "greet"
    else:
        stage = "choose_language"

    session = db_repo.create_session(
        learner_id=learner.id if learner else None,
        language=language,
    )

    starting_state = initial_state(
        session_id=session.id,
        learner_id=learner.id if learner else None,
        language=language,
        stage=stage,
        profile=profile_from_learner(learner) if learner else None,
        # Her saved interest is a content-store skill id; resume/teach read it.
        skill_id=(learner.interest_skill or None) if learner else None,
    )

    graph = request.app.state.agent_graph
    config = {"configurable": {"thread_id": session.id}}
    result_state, _ = await timed(graph.ainvoke(starting_state, config=config))

    greeting_text = result_state["reply_text"]
    try:
        tts_result, _ = await timed(synthesize(greeting_text, language))
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
    photo: UploadFile | None = File(None),
) -> TurnResponse:
    provided = [x for x in (audio, tapped_option_id, photo) if x is not None]
    if not provided:
        raise ApiError(400, "missing_input", "Provide audio, tapped_option_id, or photo.")
    if len(provided) > 1:
        raise ApiError(
            400, "ambiguous_input", "Provide only one of audio, tapped_option_id, or photo."
        )

    graph = request.app.state.agent_graph
    config = {"configurable": {"thread_id": session_id}}

    if audio is not None:
        # An explicit language hint measurably improves Sarvam's accuracy on
        # accented/regional/code-mixed speech versus blind auto-detect --
        # important since this app is built for speakers who don't speak
        # "textbook" language. Read the session's language from the
        # checkpoint rather than trusting the client to send it.
        snapshot = await graph.aget_state(config)
        session_language = snapshot.values.get("language") if snapshot.values else None
        # While she is still choosing a language, the checkpoint holds only
        # the placeholder -- let Sarvam auto-detect instead of biasing it.
        if snapshot.values and snapshot.values.get("stage") == "choose_language":
            session_language = None

        audio_bytes = await audio.read()
        logger.info(
            "STT request: filename=%r content_type=%r bytes=%d language=%r",
            audio.filename,
            audio.content_type,
            len(audio_bytes),
            session_language,
        )
        try:
            stt_result, stt_ms = await timed(
                transcribe(
                    audio_bytes,
                    language=session_language,
                    filename=audio.filename or "audio.webm",
                    content_type=audio.content_type or "audio/webm",
                )
            )
        except SttError as exc:
            logger.error(
                "STT failed: status_code=%s message=%s", exc.status_code, exc.message
            )
            raise ApiError(502, "stt_failed", exc.message) from exc
        transcript = stt_result.transcript
    elif photo is not None:
        # Practice review: the vision model turns the photo into neutral
        # observations; the practice node does the pedagogy. Billed to the
        # stt latency slot (it is the input-understanding step of the turn).
        photo_bytes = await photo.read()
        try:
            observations, stt_ms = await timed(
                describe_practice_photo(photo_bytes, photo.content_type or "image/jpeg")
            )
        except Exception as exc:  # vision failures degrade warmly, not 500
            logger.error("photo review failed: %s", exc)
            raise ApiError(502, "photo_failed", "Could not look at the photo just now.") from exc
        transcript = None
        agent_input = f"[photo] {observations}"
    else:
        transcript = None
        stt_ms = 0

    if photo is None:
        agent_input = transcript if transcript else (tapped_option_id or "")

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
