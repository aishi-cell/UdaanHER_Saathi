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
- [x] "Log out on this phone" — the "Not you?" link is now shown for the
      whole session (not just the first moment), and clears the remembered
      login + stops the mic if it was listening. Live-verified with a real
      learner + real browser: auto-resume → link visible → still visible
      seconds later → click → back on Landing, "Talk to Saathi" enabled,
      `localStorage` cleared
- [x] Bonus bug found + fixed during that live test: `connecting` was never
      reset to `false` on a successful session start, so after logging out
      the Landing button was stuck showing "connecting..." and disabled
      forever, even with nothing in flight — she'd have been unable to start
      a new session at all. Fixed in `startSession` (`App.tsx`)

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
- [x] Second bonus bug found + fixed via a full-session live stress test: a
      broken test scenario (skill choice failed to match, desyncing the
      conversation) fed garbled/off-topic input like "nahi" into discover's
      skill-matching step, which — instead of recognizing that wasn't a
      skill at all — fired a real background build that fabricated an
      entire fake curriculum ("Basic Refusal Skills: How to Say 'No' with
      Confidence", complete with concepts and rubrics) out of nothing,
      violating the "grounded, not invented" principle in `app_plan_v2.md`.
      Never reached a real learner (the `trusted=false` gate already blocks
      it), but it's still a real, costly background job spent on noise, and
      an easy way to litter the content store with junk needing manual
      cleanup. Fixed with a new `is_plausible_skill` field on the same
      extraction call (no extra LLM call) — `discover.py` now re-asks
      instead of building when it's false

## 3. Add a Career Development Roadmap ("My Journey")
Fully shipped, in two passes: a v1 that auto-tracks the 4 milestones
observable from inside a session, then a second pass adding a way for her
to self-report the 2 that happen off-platform (a real customer, a real
sale) — see the last item below for how that's scoped.
- [x] Milestone model: `started_skill`, `made_product`, `learned_pricing`,
      `completed_skill` (auto-tracked) + `found_customer`, `first_paid_order`
      (modelled, not yet markable) — `app/agent/milestones.py`
- [x] Backing data model/persistence: new `career_milestones` table
      (learner_id, skill_id, milestone_id, achieved_at), idempotent marking,
      cleaned up by `delete_learner` — `db.py`
- [x] Auto-marked at the natural point each becomes true: `started_skill` on
      entering `teach`, `made_product` only on an actual practice photo (not
      a voice skip — real evidence), `learned_pricing` at the end of `earn`,
      `completed_skill` in `wrapup` when every must-land concept is strong
- [x] "My Journey" screen: `JourneyView.tsx` — large icons (check vs. circle),
      minimal bilingual text, a highlighted next-step banner, and a plain-
      language hint on the two not-yet-markable milestones ("tell Saathi
      when this happens")
- [x] Reachable any time once she's identified, without spending a
      conversation turn — a REST endpoint (`GET /api/learner/{id}/journey`)
      + a small persistent button, not threaded through the turn-based graph
- [x] Voice query "Saathi, mere liye aage kya hai?" answered *in conversation*
      at the three most natural checkpoints, without a new intent-detection
      mechanism: **resume**'s welcome-back (both the typed/remembered-login
      path and the voice-PIN path independently, since the latter builds its
      own reply), **teach**'s existing `progress_query` interception (now
      also names the next career milestone, not just lesson progress), and
      **wrapup**'s closing narration. Doing it at literally *every* point in
      every stage (viva/reteach mid-question, practice, earn, etc.) would
      need the same interception rewired into each one — deferred, these
      three cover the moments she'd actually ask this. Live-verified against
      the real LLM: a resumed learner correctly heard her next milestone
      unprompted, and asking mid-lesson got a reply blending lesson progress
      with the career milestone in one natural sentence
- [x] Bug found + fixed via a full-session live stress test (teach through
      viva/reteach with a deliberately vague, off-topic answer repeated on
      purpose): the `progress_query` classifier added for roadmap item 4
      (viva/reteach share `VivaGrade.progress_query`) was over-triggering on
      weak/rambling answers that weren't actually asking about progress --
      it would hold the same question and re-ask it, live-observed stuck for
      5 turns straight in `viva`. Tightened `GRADE_INSTRUCTION` in `viva.py`/
      `reteach.py` (and `teach.py`'s intent classifier, same risk) to require
      an unambiguous progress question and default to grading otherwise.
      Re-ran the identical stress scenario after the fix: 0 repeats across 6
      viva turns with the exact same input that broke it before
- [x] A way for her to report `found_customer` / `first_paid_order` from a
      future session. Scoped conservatively to avoid changing the
      experience for everyone: `resume.py` actively asks — warmly, easy to
      skip, no pressure either way — only for the specific subset of
      returning learners whose next pending milestone for a skill is one of
      these two (i.e. she's already made a product and priced it last
      time). Every other returning learner's welcome is unchanged, same
      single turn as before. Also unified the voice-PIN login path
      (`greet.py`) to chain into `resume.run()` instead of duplicating its
      welcome-back logic inline, so both entry paths share one
      implementation going forward.
      Live-verified against the real LLM (not mocked), both directions: a
      "yes, a customer found me" answer was celebrated warmly and correctly
      persisted (confirmed via the journey endpoint); a "not yet" answer
      got zero-pressure reassurance and moved on normally; an unclear reply
      was gently re-asked rather than assumed either way

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
- [x] Third bug found + fixed (by re-reading `get_progress()` while working
      on something else): the progress screen's lesson titles and concept
      labels were the raw internal ids verbatim (e.g. "c-tape-basics"), not
      real words — the docstring even said so ("stay placeholders until the
      content loader is wired in", never finished). `db.py`'s `get_progress`
      now resolves both from the content store in her own language, with a
      graceful fallback to the raw id for anything that isn't a real
      skill/concept (old test fixtures, mainly). Live-verified against a
      real learner mid-`viva`: every concept and the skill title came back
      in real Hindi words
- [x] Simplify the progress screen further toward icons/symbols over
      text/numbers — `ProgressView.tsx`'s stat row led with bare numbers
      ("1", "1", "1"); now each leads with a large icon (book/lightbulb/
      medal) with the count as a secondary cue, matching how the % ring is
      already treated. Concept badges now carry a mastery symbol (check /
      dashed circle / plain circle) alongside their colour, so mastery
      reads without parsing the word or telling green from amber apart.
      Bonus fix noticed while here: the "Skill" stat was a hardcoded literal
      `1` (always showed "1", meant nothing) — now shows her actual skill
      name. Verified visually via the `?ui-demo=1` screenshot driver
      (frontend-only, no backend needed)

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
- [x] Asking about the larger career journey by voice — live-verified at the
      resume welcome-back and mid-teach progress_query checkpoints (see §3);
      not covered at every possible point in every stage
- [x] Viewing the My Journey screen — live-verified end-to-end: a real
      learner created via the API, reached `teach` (marking `started_skill`),
      confirmed the button appears, opens the overlay, shows the right
      achieved/unachieved state and next-step text, and closes cleanly
- [ ] Small/older phone check
- [ ] Every newly added language (none added yet)

---

## Notes
- This file tracks the roadmap in `new_roadmap.md`. It does not replace
  `docs/app_plan_v2.md`, which is the canonical product/architecture doc — the
  roadmap above is layered on top of that plan, not a replacement for it.
- The Career Roadmap (item 3) is now fully shipped, including the
  self-reported off-platform milestones. Language expansion (item 7) is the
  only substantial item left, and it's a genuinely different kind of work —
  it needs your decision on which languages/order, plus real translation
  and native-speaker review per language, not more code from here.
  Latency benchmarking (item 5) also remains, blocked on real measurement
  infrastructure rather than a coding task.
