# Decisions log

One line per stack/scope decision, dated.

- 2026-07-10: Stack pinned per spec v1.0 (FastAPI + LangGraph + Sarvam + OpenAI backend, Vite/React/TS frontend, SQLite via SQLModel).
- 2026-07-10: Backend Python/venv managed via `uv` instead of plain `venv`/`pip` (per team preference); `uv sync` replaces `pip install`, `uv run` replaces manual venv activation. Deps in `backend/pyproject.toml` remain the same packages the spec calls for.
- 2026-07-10: `npm run dev` must be passed `--host 127.0.0.1` in this environment; Vite's default bind was unreachable via IPv4 loopback during local verification.
