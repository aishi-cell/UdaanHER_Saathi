# UdaanHER Saathi — Feature & Efficiency Roadmap

## Context

UdaanHER Saathi is a voice-first mentor app for low-literacy rural women: near-buttonless UI,
Hindi/Gujarati/Punjabi/English via Sarvam (Saaras v3 STT + Bulbul v3 TTS), OpenAI reasoning
through a one-node-per-turn LangGraph, and a two-speed content architecture (a slow-lane
Content Builder that grounds skills in real YouTube tutorials, a fast-lane voice mentor that
teaches from the cached result). The goal is to substantially grow the feature set — a career
roadmap, a learning roadmap, a formal digit-code login, a simpler UI, faster/cheaper AI, and
eventual expansion beyond Hindi.

This roadmap is written against what's **already built** (confirmed by reading the code and
`docs/decisions.md`, not assumed) so each epic states the real gap instead of re-proposing
something that exists. Two things are more built than the original ask implied:

- **Digit-code login already exists.** `greet.py` + `db.py` already do new/returning branching,
  a spoken 4-digit PIN (PBKDF2-hashed, `find_learner_by_pin`), consent-gated remembering, and a
  2-attempt retry before a graceful fresh start. The gap is robustness, not the concept.
- **A per-skill earning close already exists.** `earn.py` narrates what to make/sell and how to
  find customers at the end of every skill, from grounded `EarningNotes`. What's missing is a
  *persistent, cross-visit* roadmap view — that's the real net-new ask.

## Guiding principle

Reuse working plumbing — PIN auth, `choose_language`, the content store's `pick_language`,
LangGraph's one-node-per-turn stage machine, the existing Playwright driver — rather than
rebuild it. Each epic below names what stays, what's new, and the concrete files involved.

---

## Epic 1 — Harden the digit-code login

**Gap:** the only PIN input channel is voice. STT mishearing a spoken digit is the single most
likely lockout point, and today a second miss abandons her saved profile entirely (fresh start).

- Add a tap-based numeric keypad as a fallback `UICommand` (e.g. `enter_pin`), offered alongside
  voice from the first PIN prompt — not only after two failures. Mirrors the existing
  `show_options` tap pattern in `Renderer.tsx` / `OptionCards.tsx`.
- Remember the device: store her PIN (or a session token derived from it) in `localStorage` so
  the same phone reconnects without re-speaking anything; voice/tap PIN stays the path for a new
  device.
- Widen the retry budget now that a keypad exists — voice-only justified the tight 2-attempt cap
  in `greet.py`; a tap fallback removes most of that pressure.
- Files: `backend/app/agent/nodes/greet.py` (accept a typed PIN alongside the spoken one),
  `frontend/src/components/` (new PIN pad component), `frontend/src/types.ts` + `Renderer.tsx`
  (new UI command variant), `backend/app/models/db.py` (PIN infra already there, unchanged).

## Epic 2 — Onboarding polish

**Current:** `greet` (name + new/returning) → `choose_language` (voice-first, canned trilingual
prompt, tappable cards) → `discover` (skill interest) → `assess` (diagnostic → per-concept gap
estimate). This is already a considered, tested flow (multiple live-run bug fixes logged in
`decisions.md`) — treat this epic as targeted tightening, not a rebuild:

- Combine ack + next-question at the `discover`/`confirm_profile` transitions where
  `decisions.md` (2026-07-11) notes an extra filler turn was accepted as a known cost — worth
  revisiting now that efficiency is a priority (Epic 5).
- `discover`'s 4 skill cards are still a hardcoded placeholder outside `tailoring` (documented
  gap) — replace with the live content-store skill list once enough skills are seeded/trusted.

## Epic 3 — Career Development Roadmap (new)

**Gap:** nothing persists across visits beyond mastery rows and one skill's earning notes.
There's no "here's where this is headed" view.

- New data: a lightweight `career_milestones` (or similar) table/column set keyed on learner —
  skill(s) attempted, earning notes already reached, and simple next-milestone markers (e.g.
  "made her first sellable item," "quoted a price," "found a first customer"). Reuses the same
  learner id as `concept_mastery`/`lesson_progress`.
- New voice access: a roadmap becomes askable any time ("Saathi, aage kya hai mere liye?"), not
  only narrated once at `earn`. Cheapest version: a small intent check on idle/turn input that
  routes to a new lightweight node reading the milestone data and narrating it via
  `ask_conversational` — no new LLM call needed for the factual part, since it's just formatting
  already-known data.
- New screen: a "My Journey" timeline view alongside `ProgressView`, fed by the same data,
  reachable from a tap or spoken request.
- This is the largest net-new engineering item in the roadmap — new table, new node, new screen.

## Epic 4 — Voice-based Learning Roadmap (new, scoped to the *current* skill)

**Gap:** `assess` already computes `learning_path` (ordered gap-concepts) in
`backend/app/agent/nodes/assess.py`, but it's internal state only — never spoken to her, and
only shown visually once `ProgressView` renders mid-teach.

- Right after `assess` resolves (or on request during `teach`), narrate the path: "Yeh cheezein
  hum seekhenge: X, Y, Z. Chaliye X se shuru karte hain." Pure string assembly from the existing
  `learning_path` + concept labels (`store.pick_language`) wrapped in one cheap
  `ask_conversational` call for warmth — no new extraction/LLM-heavy step.
- Make it re-askable mid-session ("ab tak kya seekha, aage kya hai") via the same lightweight
  intent check proposed in Epic 3 — the two roadmaps (career-wide, current-skill) share that
  entry point and differ only in which data they read.

## Epic 5 — AI efficiency

- **Biggest known lever, already identified but not done** (`decisions.md`, 2026-07-14): merge
  each node's extract-structured-data call and its conversational-reply call into **one**
  structured call. Saves ~1s per turn across the board; do this first since every other epic's
  new nodes benefit from the same pattern going forward.
- Audit per-node model choice against the T24 finding that `gpt-5-mini` was *slower* net than
  `gpt-5.1` on this account — re-measure before assuming a "cheaper model" lever exists.
- Add OpenAI prompt caching for the static parts of each node's system/instruction scaffolding
  (concept labels, persona rules) that repeat every turn.
- Turn the existing `?debug=1` latency overlay (`lastTurn.latency_ms`) into a standing dev-only
  log/metric so a regression is caught immediately, not rediscovered live.
- Target: bring per-turn latency from the current 5–8s toward 3–4s.

## Epic 6 — UI simplification

**Current:** already close to buttonless — one talk button, tappable option cards as a fallback,
an animated avatar, no navigation chrome. Push further rather than starting over:

- Drop the raw backend-status dot from production builds — it's a dev signal, not something a
  real user should see or need to interpret.
- Larger tap targets / higher contrast on option cards and the new PIN pad (Epic 1) — assume
  older/smaller phones and no reading.
- `ProgressView` is the one screen that's still numbers/English-label heavy ("Lessons", "Ideas
  solid") in an app explicitly built to avoid requiring reading — replace with icon-first,
  voice-narrated equivalents; the ring/percent visual can stay as a supporting cue, not the
  primary channel.

## Epic 7 — Regional language expansion

**Current:** `hi-IN`, `gu-IN`, `pa-IN`, `en-IN` wired in
`backend/app/agent/nodes/choose_language.py`. Sarvam's Saaras v3 / Bulbul v3 already cover
roughly 11 Indian languages total, so most of the remaining ones (Bengali, Kannada, Malayalam,
Marathi, Odia, Tamil, Telugu) need **no new audio-model integration** — this is config plus
content-translation work:

1. Add each language to `LANGUAGE_OPTIONS` + the `_PATTERNS` keyword-match table in
   `choose_language.py`.
2. Extend each skill's `content/store/<skill>/curriculum.json` multi-language labels (already
   read via `store.pick_language()`) — needs an LLM-assisted translation pass plus the same
   human-review/`trusted` gate the Content Builder already uses for grounded content.
3. Regression-test each new language with the existing harness:
   `backend/scripts/live_onboarding_transcript.py` → `docs/transcripts/onboarding_<lang>.md`,
   same pattern already used for `hi-IN`/`gu-IN`.
4. Roll out one language at a time, cheapest-to-translate first.

**Audio model recommendation: keep Sarvam (Saaras v3 STT + Bulbul v3 TTS); don't switch.**
It was deliberately chosen and already tuned for this exact audience — code-mixed, accented,
low-literacy rural speech (`decisions.md`, 2026-07-11's STT accuracy pass) — and its language
coverage already spans nearly every language on the likely rollout list. Reconsider only if a
*specific* target dialect Sarvam doesn't cover comes up; in that narrow case, pilot AI4Bharat's
open-source stack (IndicTrans2 / IndicWav2Vec / Indic-Parler-TTS) for that one language rather
than replacing Sarvam wholesale. Generic multilingual options (Google Chirp, OpenAI Whisper) are
not a good fit here — they're not tuned for this accent/code-mixing profile the way Sarvam
already is, and the team's own testing (documented in `decisions.md`) is what led to the current
choice.

---

## Suggested sequencing

- **Phase A — foundation:** Epic 5 (merge extract+reply — the biggest, lowest-risk efficiency
  win) + Epic 1's PIN-pad fallback (closes a real lockout risk today).
- **Phase B — flagship features:** Epic 3 (career roadmap) + Epic 4 (voice learning roadmap) —
  the two "show her a roadmap" asks; they share the same new intent-routing entry point and a
  good chunk of frontend work.
- **Phase C — polish:** Epic 2 (onboarding tightening) + Epic 6 (UI simplification).
- **Phase D — scale:** Epic 7, one regional language at a time.

## Verification approach (once implementation begins)

- Backend: `uv run pytest` (existing suite), new tests per node/table change mirroring existing
  files (`test_agent_graph.py`, `test_onboarding.py`, `test_session_and_progress.py`).
- Live regression: the existing `backend/scripts/live_*_transcript.py` scripts against
  `docs/transcripts/`.
- End-to-end/UI: the `run-udaan-hersaathi` skill's Playwright driver already exists for exactly
  this — use it to verify each new flow (PIN pad, roadmap screen) before calling it done.

## Explicitly out of scope here

- No change to the two-speed Content Builder architecture (plan v2) — it's solid as-is.
- No reasoning-backend swap — OpenAI stays, per the existing decision.
- No code changes in this pass. This document is the roadmap; each epic gets its own
  plan-mode pass (or a dedicated task) when you're ready to build it.
