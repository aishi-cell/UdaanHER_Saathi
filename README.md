# UdaanHer Saathi

UdaanHer Saathi is a voice-first web app where an AI mentor converses with a low-literacy woman in her own language and drives the entire screen itself. The MVP ships two features end to end: a voice onboarding that gets to know the learner and saves her profile, and a teach-viva-reteach loop that delivers one vocational lesson, checks understanding conversationally, and re-teaches whatever is shaky. See `docs/spec.pdf` for the full technical contract and `docs/tasks.pdf` for the task-by-task build plan.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (manages Python for the backend; no separate Python install needed)
- [Node.js](https://nodejs.org/) 20+ and npm (for the frontend)
- git

## Run the backend

```
cd backend
uv sync
uv run uvicorn app.main:app --reload
```

Backend serves at `http://127.0.0.1:8000`.

## Run the frontend

```
cd frontend
npm install
npm run dev -- --host 127.0.0.1
```

Frontend serves at `http://127.0.0.1:5173`.

## Run tests

```
cd backend
uv run pytest
```

## Environment variables

Copy `.env.example` to `backend/.env` and fill in real values (see `docs/spec.pdf` Section 5). Never commit `backend/.env`.
