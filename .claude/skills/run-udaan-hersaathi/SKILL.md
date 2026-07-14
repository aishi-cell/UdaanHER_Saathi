---
name: run-udaan-hersaathi
description: Run, start, drive, or screenshot the UdaanHer Saathi app — FastAPI backend on :8000 plus Vite React frontend on :5173 — and verify UI changes end-to-end with the committed Playwright driver (landing page, language picker, session flow).
---

# Run UdaanHer Saathi

Voice-mentor web app: FastAPI backend (`backend/`, port 8000) + Vite React
frontend (`frontend/`, port 5173). Drive it with the committed Playwright
driver — no `chromium-cli` needed. All paths below are relative to the
repo root.

## Prerequisites

- Node (frontend deps include `playwright-core` as a devDependency)
- `uv` (backend is a uv-managed FastAPI project)
- `backend/.env` — copy `.env.example` to `backend/.env` and fill in real
  keys (Sarvam STT/TTS + OpenAI). Without it the session flow fails.
- A Chromium: the driver auto-finds the Playwright browser cache
  (`%LOCALAPPDATA%\ms-playwright` / `~/.cache/ms-playwright`), else falls
  back to installed Edge/Chrome. Override with `PW_BROWSER_PATH` or
  `PW_CHANNEL=msedge`.

## Setup

```bash
cd frontend && npm install
```

## Run (agent path)

Start both servers in the background:

```bash
cd backend && uv run uvicorn app.main:app --port 8000
```

```bash
cd frontend && npm run dev   # Vite, ready in ~2 s on http://localhost:5173
```

Confirm the backend is up before driving:

```bash
curl -s http://localhost:8000/health   # {"status":"ok",...}
```

Then drive the app. Screenshots land in `shots/` (gitignored):

```bash
node .claude/skills/run-udaan-hersaathi/driver.mjs landing   # landing, desktop + mobile (frontend only)
node .claude/skills/run-udaan-hersaathi/driver.mjs picker    # language picker states (frontend only)
node .claude/skills/run-udaan-hersaathi/driver.mjs ui-demo   # every UICommand via ?ui-demo=1 (frontend only)
node .claude/skills/run-udaan-hersaathi/driver.mjs session   # full flow to live conversation (needs backend)
```

`session` clicks Talk to Saathi → picks a language → Continue, captures the
connecting state ("Saathi आ रही हैं…"), waits up to 45 s for the greeting,
and captures the ready conversation view. It exits non-zero on console
errors or if the session never becomes ready. **Look at the screenshots.**

## Run (human path)

Same two server commands in two terminals, then open
http://localhost:5173 in a browser. Useless headless.

## Test

```bash
cd frontend && npx tsc -b     # typecheck; exit 0 expected
```

## Gotchas

- **Port 8000 already bound** (`[Errno 10048]` on Windows): a backend is
  already running — don't start a second one; `curl /health` and reuse it.
- **Session creation is slow (5–15 s):** `POST /api/session` does an LLM +
  TTS greeting warm-up. The UI shows the session screen with a
  "Saathi आ रही हैं…" status while connecting; the driver polls for that
  text to disappear rather than using a fixed wait.
- **Microphone:** the driver launches Chromium with
  `--use-fake-ui-for-media-stream --use-fake-device-for-media-stream` and
  grants the `microphone` permission, so no permission prompt blocks the
  flow. It deliberately does **not** press the talk button — a real turn
  sends audio through paid STT/LLM/TTS APIs.
- **Entrance animations:** the landing page staggers in over ~1 s; the
  driver waits before screenshotting. If you script your own shots, do the
  same or you'll capture half-faded UI.
- **Frontend without backend:** `landing` and `picker` flows work with only
  Vite running; the red status dot top-right just means backend unreachable.

## Troubleshooting

- `Backend not reachable on :8000` from the `session` flow → start the
  backend (see Run) and re-check `curl -s http://localhost:8000/health`.
- `No browser found` from the driver → `npx playwright install chromium`,
  or set `PW_CHANNEL=msedge` (verified working) / `PW_BROWSER_PATH`.
- Driver exits 1 with `console errors:` listing React errors → the app
  rendered but is broken; fix those first, screenshots may still be useful.
