# Decisions log

One line per stack/scope decision, dated.

- 2026-07-10: Stack pinned per spec v1.0 (FastAPI + LangGraph + Sarvam + OpenAI backend, Vite/React/TS frontend, SQLite via SQLModel).
- 2026-07-10: Backend Python/venv managed via `uv` instead of plain `venv`/`pip` (per team preference); `uv sync` replaces `pip install`, `uv run` replaces manual venv activation. Deps in `backend/pyproject.toml` remain the same packages the spec calls for.
- 2026-07-10: `npm run dev` must be passed `--host 127.0.0.1` in this environment; Vite's default bind was unreachable via IPv4 loopback during local verification.
- 2026-07-10: T02 smoke tests (`scripts/smoke_sarvam.py`, `scripts/smoke_openai.py`) pass with real keys. `TTS_SPEAKER=priya` used as a placeholder valid `bulbul:v3` voice to unblock the smoke test only — T06 does the deliberate 3-speaker audition and will overwrite this. `smoke_sarvam.py`'s STT half is still unexercised: no fixture WAV has been recorded yet, so it currently no-ops with a SKIP message instead of failing.
- 2026-07-10: pytest tests marked `live` (hit real Sarvam/OpenAI APIs) are excluded from the default `uv run pytest` via `addopts = '-m "not live"'` in `backend/pyproject.toml`, so the everyday test command stays fast, free, and network-independent. Run `uv run pytest -m live` to exercise them deliberately.
- 2026-07-10: T06 generated 4 `bulbul:v3` Gujarati candidates (priya, pooja, kavya, shreya) into `backend/tests/live_output/candidate_<speaker>.mp3` for a human listen — speaker choice still pending a human pick (Claude cannot listen to audio); `TTS_SPEAKER=priya` remains the placeholder until decided.
- 2026-07-11: T08's `content/assets/earcon.mp3` was synthesised programmatically (a soft two-tone chime via `lameenc`, no ffmpeg needed) rather than sourced/recorded, since no audio-authoring tool was available. It's checked into `content/assets/` per spec and duplicated into `frontend/public/earcon.mp3` so Vite's dev server can serve it directly; revisit with a proper sourced chime if the placeholder doesn't feel right in the demo.
- 2026-07-11: `POST /api/session` (T09) doesn't exist yet, so the frontend generates its own `session_id` client-side via `crypto.randomUUID()` on mount. T07's backend stub accepts any `session_id`. T09/T11 will replace this with a real session created via `/api/session`.
