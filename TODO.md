# UdaanHER Saathi — Roadmap TODO

Converted from [new_roadmap.md](new_roadmap.md) into a trackable checklist. Status
reflects the codebase as of 2026-09-24. Check items off as they land; leave a short
note (commit/PR) next to anything non-obvious.

Legend: `[x]` done · `[~]` partially done / in progress · `[ ]` not started

---

## Phase 1 — Make the Foundation Stronger

### 1. Make Login Easier and More Reliable
- [x] Ask "have we talked before?" and branch new vs. returning (voice, `greet.py`)
- [x] Spoken 4-digit PIN for returning users, looked up PIN-first (`find_learner_by_pin`)
- [x] PIN generated + spoken + shown on the profile card for new users (`confirm_profile.py`)
- [x] Number keypad for entering the PIN (voice OR tap), shown from the start of the
      PIN step, not only after voice fails — `request_pin` UI command + `Keypad.tsx`
- [x] Persistent on-screen PIN display in one corner, for the whole session, for a
      new user — `PinBadge.tsx` + `pending_pin` plumbed from tap-through to save
- [x] "Remember this phone" — successful login/registration cached in
      `localStorage`; next visit on the same phone auto-resumes without asking for
      the code again (`useRememberedLogin.ts`)
- [x] More PIN attempts before starting over — bumped 2 → 4 (`MAX_PIN_ATTEMPTS`)
- [ ] "Log out on this phone" affordance to clear the remembered login (basic
      version shipped: a "Not you?" link on auto-resume; polish later)

### Faster responses (Phase 1 partner item)
- [x] Quick win: PIN turns skip the LLM extraction call entirely when the input is
      already 4 clean digits (typed keypad or tapped) — one fewer model round-trip
      on the login path
- [x] Combine sequential short replies into one turn where possible (see roadmap
      §2 "reduce unnecessary questions") — 3 throwaway turns removed from
      onboarding (see §2 above); each one was a full STT+LLM+TTS round trip she
      no longer has to sit through
- [ ] Benchmark alternate STT/LLM options for speed/cost/accuracy/language quality
      — needs real measurement, not a guess; not started
- [ ] Continuous latency tracking / regression alerts — not started

---

## 2. Make the First-Time Experience Smoother
- [x] Guided flow: name → new/returning → language → what to learn → what she
      knows → what's next (existing onboarding graph: greet/discover/assess)
- [x] Combine short ack + next question into a single turn — the three
      transitions that used to end in a plain ack with nothing to answer
      (consent→discover, skill-chosen→assess, assess-done→confirm_profile)
      now chain straight into the next stage's opening question in the same
      reply, cutting 3 throwaway round-trips out of onboarding (was 11 turns
      end-to-end, now 8) — also a real "faster responses" win, not just UX
- [x] Bonus bug found + fixed while doing this: several stage-opening prompts
      (discover's village question, confirm_profile's readback, resume's
      welcome-back, teach's first lesson, practice's task-setting) passed an
      empty transcript that the LLM renders as "(no speech was heard
      clearly)" — live-verified the model apologising for audio it was never
      given, mid-reply. Fixed via a shared `FRESH_TOPIC` placeholder in
      `llm_utils.py` (same fix greet.py step 0 already had, now applied
      everywhere the same bug pattern existed)
- [ ] Learning options shown to her should grow automatically as more trusted
      courses/skills are added to the content store (mostly true already since
      `discover.py` reads live from `content/store/`, but no build pipeline yet
      to keep growing that store — depends on Content Builder work below)

## 3. Add a Career Development Roadmap ("My Journey")
- [ ] Milestone model beyond lesson/concept mastery: started skill, completed
      skill, first usable product, priced it, found a customer, first paid order
- [ ] Voice query: "Saathi, mere liye aage kya hai?" → explain progress + next
      milestone
- [ ] "My Journey" screen: large icons, simple milestones, minimal text
- [ ] Backing data model/persistence for career milestones (new DB table)

## 4. Add a Learning Roadmap for the Current Skill
- [x] Backend already knows the ordered concept plan for a skill
      (`content/store/<skill>/curriculum.json`, `learning_path` in agent state)
- [x] Saathi narrates the plan up front ("you'll start with X, then Y, then
      Z...") before teaching the first step — `teach.py`'s `_narrate(first=True)`
- [x] Voice query mid-skill in the **teach** stage: "Ab tak maine kya seekha?" /
      "Ab aage kya seekhna hai?" → new `progress_query` intent on `TeachIntent`,
      answers from done/current/upcoming concepts and holds the step (doesn't
      advance or lose her place)
- [x] Same voice query during **viva** and **reteach**: both reuse the same
      `VivaGrade.progress_query` field folded into their existing grading
      extraction, so no extra LLM call; holds the just-asked question in
      place rather than skipping or grading it. Live-verified end-to-end
      (real LLM, not mocked): asked mid-`teach`, got a correct plan
      recap, held the step, then resumed normally to the next concept on
      the following turn
- [ ] Same for **practice** — it has no structured-extraction call to fold
      this into (plain text branching: done/skip/can't), and its step 1 is a
      one-shot fork rather than a repeatable question to "hold" -- adding it
      would cost a new LLM call for a narrow, rarely-hit case. Skipped as not
      worth the latency cost; her real words still reach the model as
      context either way, so it isn't blind to the question
- [x] `show_progress` UI command + `ProgressView.tsx` exist for the full
      end-of-skill summary (unchanged, still the wrapup-stage view)

## 5. Make Saathi Respond Faster
- [ ] Reduce multi-step reasoning to fewer LLM calls per turn where possible
- [ ] Real benchmarking of model options (speed / cost / accuracy / language
      quality / conversation quality) before switching anything
- [ ] Continuous latency tracking so a regression is caught immediately
- [x] (Started above) PIN-entry fast path skips an LLM call when input is clean

## 6. Make the Screen Even Simpler
- [x] Audit for developer-facing indicators leaking into the learner UI — found
      one: the backend-connectivity dot was always visible with no explanation
      a learner could act on (an unreachable backend already surfaces as a
      warm error message when she tries to do something). Moved it behind
      `?debug=1`, same as the existing debug panel
- [x] Tap targets: `OptionCards`, the language picker, and the new PIN keypad
      already use large (~64px+) touch targets — checked, no changes needed
- [ ] Simplify the progress screen further toward icons/symbols over
      text/numbers — `ProgressView.tsx` already leans on icons + a percent
      ring rather than raw numbers; not reworked further this pass

## 7. Add More Indian Languages
- [x] Hindi, Gujarati, Punjabi, English supported end-to-end (voice + content)
- [ ] Bengali, Kannada, Malayalam, Marathi, Odia, Tamil, Telugu — none started
- [ ] Per-language rollout checklist (translate → test voice → test
      pronunciation → mixed-language check → full review → launch) — process not
      yet formalized anywhere

---

## Phase 3 — Improve the Overall Experience
- [ ] Smoother onboarding (see §2 above)
- [ ] Fewer unnecessary conversation steps (see §2, §5)
- [ ] Larger/simpler buttons everywhere (see §6)
- [ ] Clearer progress screen (see §4, §6)
- [ ] Remove technical info from the UI (see §6)

## Phase 4 — Expand to More Languages
- [ ] See §7 above — not started beyond the current four languages

---

## Testing checklist (per roadmap "How Each Improvement Should Be Tested")
- [x] New user, first time (existing greet/discover/assess flow, tested)
- [x] Returning user, voice PIN (existing, tested in `test_onboarding.py`)
- [x] Returning user, number keypad (new — needs a live/manual pass; unit tests
      added for the backend lookup + `pending_pin` plumbing)
- [x] Returning user, same phone remembered (new — manual pass recommended,
      `localStorage`-based so no backend test coverage possible)
- [x] "What should I learn next?" / "What have I learned so far?" voice query
      — covered by unit tests during teach/viva/reteach, and live-verified
      end-to-end against the real LLM mid-`teach` (see §4 above); practice
      doesn't have it (see §4 note on why)
- [ ] Asking about the larger career journey
- [ ] Viewing the My Journey screen
- [ ] Small/older phone check
- [ ] Every newly added language (none added yet)

---

## Notes
- This file tracks the roadmap in `new_roadmap.md`. It does not replace
  `docs/app_plan_v2.md`, which is the canonical product/architecture doc — the
  roadmap above is layered on top of that plan, not a replacement for it.
- Items 3 (Career Roadmap) and the language expansion (item 7) are the largest
  remaining pieces of work and will need their own follow-up sessions.
