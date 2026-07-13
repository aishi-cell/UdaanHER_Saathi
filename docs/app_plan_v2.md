# UdaanHer Saathi — App Plan v2 (generalized, grounded, earning-first)

**Supersedes** the fixed-curriculum content model in the original spec (§9, §11) and the
tailoring-only `curriculum_plan.md`. This is a plan-level rethink, not a task tweak — record
the switch in `docs/decisions.md` before building.

## The one-line vision

A **voice mentor** for rural women that figures out what she already knows, then teaches her —
in short, spoken, personalized lessons **grounded in real tutorials, not invented** — how to
**earn** from a vocational skill. Any skill. Nothing about a specific trade is hardcoded.

## Four principles (every design choice serves these)

1. **Earning-first.** The goal is income, not a certificate. Every skill's path ends in
   *make something sellable → price it → find customers*, not just technique.
2. **Voice-first.** Voice is the primary interface. She never has to read or tap. Visuals
   (a real video clip, or a generated diagram) are *optional aids* the mentor offers — never
   required to follow the lesson.
3. **Generalized, not hardcoded.** No skill lives in code. The teaching engine is
   skill-agnostic; skills are data the system *produces*. The "popular rural skills" are just
   the pre-seeded library, not a cage.
4. **Grounded, not invented.** Content is distilled from *real* YouTube tutorials (via
   transcript / STT-translate) — so it's trustworthy for a livelihood, where wrong advice has
   real cost. The mentor synthesizes and narrates; it does not hallucinate a curriculum, and
   it does not produce videos.

---

## The architecture: a two-speed system

The hard constraint (see *Feasibility* below) is that YouTube search + transcript fetch is
**quota-limited and too slow for the live conversation**. That single fact splits the app into
two lanes — which also cleanly resolves "generalized *and* content-we-create":

### Slow lane — the Content Builder (offline / background, cached)
Turns a *skill or concept* into reusable, grounded teaching material. Never blocks a conversation.

```
skill/concept request
  → YouTube Data API search  (find 3–5 candidate tutorials)   [batched, cached]
  → get transcript           (youtube-transcript-api;
                              fallback: Sarvam STT-Translate on the audio)
  → LLM distills             (concept map, ordered micro-steps, earning notes,
                              common mistakes, viva questions + sample answers)
  → validate + (optional) human review  → mark "trusted"
  → cache in content store    (the same JSON shape the teach engine already reads)
```
The output is exactly the curriculum/rubric/visual-aid shape the existing engine consumes —
so **generated content and hand-authored content are interchangeable.**

### Fast lane — the live Voice Mentor (per turn, cheap + fast)
Everything the learner experiences. Reads from the cached store; generates only *sequencing
and narration* live.

```
greet → choose skill (voice) → ASSESS (diagnose what she knows/doesn't)
  → build her personalized path (pick only her gap-concepts from the store)
  → for each micro-lesson:
        narrate the step (spoken, in her language, from cached teaching notes)
        offer an aid ONLY if it helps:  real video clip  ▸ else  generated SVG diagram
        let her ask / repeat / continue (voice)
        quick conversational check → grade concept (strong/shaky)
  → reteach shaky concepts differently (different analogy / a video / a diagram)
  → EARNING module: what to make, what it sells for, where to find buyers
  → wrap up + remember her (mastery persisted) → next visit resumes at her gaps
```

**What's "on the go":** the *assessment, path selection, narration, and visuals* are live.
The *raw sourcing* (video + transcript) is pre-built and cached. A skill nobody has asked for
before triggers a background build — *"let me put that together for you"* — then it's instant
for everyone after.

---

## The learner journey (voice-only walkthrough)

1. **Pick a language, then a skill — by voice.** "I want to earn from mehndi." No fixed menu;
   she can name anything. (Seeded skills answer instantly; a new one kicks off a build.)
2. **Assess (the differentiator).** A warm 3–5 min conversation, *not a quiz*: story questions
   that reveal what she already does and where she's shaky. Output: a per-concept
   knowledge estimate for this skill.
3. **Personalized path.** The mentor silently assembles a short sequence of micro-lessons
   covering **only her gaps** — skipping what she already knows. This is why assess-first matters:
   a woman who already sews doesn't sit through "this is a needle."
4. **Teach, micro-lesson by micro-lesson.** Each is one spoken idea (30–90s), optionally with:
   - a **real video clip** if the store has a good, watched one for that concept, or
   - a **generated diagram** (LLM→SVG) if not — simple, labeled, low-literacy-friendly.
5. **Check conversationally.** One friendly question per concept; graded strong/shaky against
   cached sample answers. Never called a test.
6. **Reteach what's shaky** — differently: a new analogy, a different clip, a diagram.
7. **Earning module.** The point of the whole thing: *"Here's a simple blouse you can make and
   sell for ₹X; here's who buys — neighbours, the local shop, SHG melas."*
8. **Remember her.** Mastery + earning progress persist; next visit she resumes at her next gap.

---

## Content model (generalized — no skill in code)

Same three files, now **populated by the builder**, not hand-authored per trade:

- `content/store/<skill>/curriculum.json` — concepts + ordered micro-steps + teaching notes +
  **earning notes**, distilled from real tutorials. Carries provenance (`source_video_ids`) and
  a `trusted` flag.
- `content/store/<skill>/rubrics.json` — viva questions + `sounds_right`/`sounds_confused`
  exemplars, drawn from the same transcripts.
- `content/store/<skill>/visual_aids.json` — vetted video clips (with timestamps) per concept;
  the reteach step may only pick from here, plus the live-diagram generator as fallback.

The teach/viva/reteach engine (existing T18–T21 work) reads this shape and **never names a
skill** — so adding candle-making, mehndi, pickle-making is *building/caching data*, not coding.

---

## Feasibility findings (from research, July 2026)

| Piece | Verdict | Detail / constraint |
|---|---|---|
| Get a video's transcript | ✅ works | `youtube-transcript-api` (free, no key) for captioned videos; **fallback:** Sarvam **STT-Translate** on the audio when captions are missing. Throttled from cloud IPs → **cache, don't refetch.** |
| Understand Hindi/regional transcript | ✅ works | LLM comprehends; Sarvam **Text Translation / Mayura** handles code-mixed Hinglish → English for reasoning. |
| **Find** the right video on the fly | ⚠️ **constrained** | YouTube `search.list` = 100 units and (since **Jun 2026**) capped ~**100 searches/day** in its own bucket. **→ search offline/batched, cache concept→video maps. Never live per turn.** This is the reason for the two-speed split. |
| Generate a visual on the fly | ✅ use SVG | LLM→**SVG/Mermaid** diagrams are fast, cheap, consistent. **Avoid** diffusion/photo generation — research shows it's too detailed/inconsistent for low-literacy pictograms without fine-tuning. |
| Assess-first + adapt | ✅ well-founded | Matches current adaptive-learning research (cognitive diagnosis → adaptive check → LLM feedback; per-learner mastery graph). The DB already has `concept_mastery`. |
| Latency | ⚠️ watch | Turns already 5–8s (T24 territory). Keep the hot path to cached-read + one cheap LLM narration call; **all sourcing is off-path.** |

Sources: [Sarvam models](https://www.sarvam.ai/models) · [youtube-transcript-api](https://pypi.org/project/youtube-transcript-api/) ·
[YouTube API quota 2026](https://www.getphyllo.com/post/youtube-api-limits-how-to-calculate-api-usage-cost-and-fix-exceeded-api-quota) ·
[EasyRead pictogram study](https://arxiv.org/pdf/2603.13695) · [LLM diagram generation](https://smcleod.net/2024/10/generating-diagrams-with-with-ai-/-llms/) ·
[closed-loop adaptive learning](https://arxiv.org/pdf/2510.22559)

---

## What this reuses vs. changes in the current build

**Keep (T01–T14, most of the plumbing):** repo, config, STT/TTS services, `/api/turn` pipeline,
DB + `concept_mastery`/persistence, UI command protocol, push-to-talk frontend, LangGraph graph
skeleton, and the **greet/discover** onboarding — greet stays; discover becomes "name any skill."

**Change / add:**
- **`assess` stage** → becomes a real *diagnostic* that outputs a per-concept knowledge estimate
  (not just a starting level). This is now central, not a formality.
- **New: Content Builder** (`content/builder/`) — YouTube search + transcript/STT-translate +
  distill + cache. Offline/background job + lazy-on-first-request.
- **New: Visual generator** (`content/visuals/`) — LLM→SVG diagrams as the no-video fallback.
- **`teach`/`viva`/`reteach`** (T18–T21) → read from the **cached store** for *any* skill, not a
  single `tailoring.json`; add the **earning module** as the closing stage of every skill.
- **Content files** → move from hand-authored (`curriculum_plan.md` / T15–T17) to
  builder-produced + human-reviewed. T15–T17 become "seed & review the starter library."

---

## Open decisions (need your call before I detail the tasks)

1. **New-skill latency:** when she asks for a skill not yet in the store, do we
   (a) build it live in-session (*"give me a moment…"*, ~30–60s), or
   (b) build it in the background and say *"I'll have this ready for you shortly / next visit,"*
   offering a seeded skill meanwhile? (b) is safer; (a) is more magical.
2. **Reasoning stack:** keep **OpenAI** for the LLM reasoning, or move to **Sarvam's Chat LLM**
   for a fully-sovereign Indic stack (better code-mixed handling, one vendor)? Affects cost/latency.
3. **Seed library size for the demo:** how many skills pre-built & human-reviewed for launch
   (recommend 3–4 deep, e.g. tailoring + mehndi + pickle-making), with the builder proving
   "any skill" live on one *un*-seeded example during the demo.
4. **Human review gate:** for MVP, is builder output auto-trusted after validation, or does a
   person sign off before a generated skill can be taught? (Trust vs. speed.)
5. **Visuals in a voice-first world:** confirm visuals are *optional aids only* (a screen may be
   absent entirely) vs. an always-present supporting screen.
