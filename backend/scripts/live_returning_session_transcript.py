"""Drives a RETURNING learner's session against the real LLM (T22): a
learner row with a known PIN and partial mastery already exists; the driver
says she has been here before, flubs the PIN once (forcing the gentle
retry), then gives the right PIN -- and the session must resume teaching at
her remaining gaps, never restarting from concept one.

Usage: uv run python scripts/live_returning_session_transcript.py [hi-IN|gu-IN]
Cleans up the learner row it creates (also on failure -- a leftover row with
this PIN would poison the next run's PIN-first lookup).
"""

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

# Windows consoles default to cp1252, which can't print Devanagari/Gujarati.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from langgraph.checkpoint.memory import InMemorySaver  # noqa: E402
from sqlmodel import select  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agent.graph import compile_graph  # noqa: E402
from app.agent.state import initial_state  # noqa: E402
from app.content import store  # noqa: E402
from app.models import db  # noqa: E402

MAX_TURNS = 60
PIN = "4271"
# She mastered these last visit -- resume must NOT teach them again.
MASTERED = ["c-tape-basics", "c-measure-points"]

SCRIPT = {
    "hi-IN": {
        "returning": "Main Sunita hoon, hum pehle baat kar chuke hain",
        "wrong_pin": "nau nau nau nau",
        "right_pin": "chaar do saat ek",
        "filler": "haan theek hai",
        "continue": "haan, aage badhiye",
        "earn_more": "haan, batao kaun kharidega",
    },
    "gu-IN": {
        "returning": "Hu Sunita chu, aapde pehla vaat kari chuki che",
        "wrong_pin": "nav nav nav nav",
        "right_pin": "chaar be saat ek",
        "filler": "haa saru",
        "continue": "haa, aagal vadho",
        "earn_more": "haa, kaho kon kharidse",
    },
}


def pick_rubric_answer(result: dict, package: store.SkillPackage) -> str:
    asked = result["viva"]["question_ids_asked"]
    question = next(q for q in package.rubrics.questions if q.question_id == asked[-1])
    return question.sounds_right[0]


async def drive(language: str, script: dict, package: store.SkillPackage, learner) -> None:
    session = db.create_session(learner_id=None, language=language)
    graph = compile_graph(InMemorySaver())
    config = {"configurable": {"thread_id": session.id}}

    lines = [
        f"# Returning-learner session transcript (T22) -- {language}",
        f"Recorded: {datetime.now(timezone.utc).isoformat()}",
        f"Pre-seeded: learner `Sunita` with PIN, mastery `strong` on `{MASTERED}`",
        "Driver deliberately gives ONE wrong PIN first (forces the gentle retry).",
        "",
    ]
    stages_seen: list[str] = []
    gave_wrong_pin = False

    def log_mentor(result: dict) -> None:
        stage, step = result["stage"], result["stage_step"]
        ui_type = result["ui"].get("type", "?")
        ui_note = f" _(screen: {ui_type})_" if ui_type != "idle" else ""
        lines.append(f"**Mentor** `[{stage}/{step}]`{ui_note}: {result['reply_text']}")
        print(f"[{stage}/{step} ui={ui_type}] Mentor: {result['reply_text'][:120]}")
        if not stages_seen or stages_seen[-1] != stage:
            stages_seen.append(stage)

    state = initial_state(session_id=session.id, learner_id=None, language=language)
    result = await graph.ainvoke(state, config=config)
    log_mentor(result)

    for _ in range(MAX_TURNS):
        stage, step = result["stage"], result["stage_step"]
        if stage == "close":
            break

        if stage == "greet":
            if step == 1:
                answer = script["returning"]
            elif step in (3, 4):
                if not gave_wrong_pin:
                    gave_wrong_pin = True
                    answer = script["wrong_pin"]
                else:
                    answer = script["right_pin"]
            else:  # step 2 would mean the PIN fell through to a fresh start
                raise RuntimeError(
                    "Returning flow fell back to the new-visitor consent path "
                    "even with the right PIN available"
                )
        elif stage == "teach":
            answer = script["filler"] if step == 0 else script["continue"]
        elif stage in ("viva", "reteach"):
            answer = script["filler"] if step == 0 else pick_rubric_answer(result, package)
        elif stage == "earn":
            answer = script["filler"] if step == 0 else script["earn_more"]
        elif stage == "wrapup":
            answer = script["filler"]
        else:
            answer = script["filler"]

        lines.append(f"**Her:** {answer}")
        print(f"Her: {answer}")
        result = await graph.ainvoke({"transcript": answer}, config=config)
        log_mentor(result)
    else:
        raise RuntimeError(f"Session did not reach close within {MAX_TURNS} turns")

    # ---- verification -------------------------------------------------------
    path = result.get("learning_path") or []
    taught_mastered = [c for c in MASTERED if c in path]
    lines += ["", "---", "", f"Stages walked: `{' -> '.join(stages_seen)}`"]
    lines.append(f"Resumed learning path: `{path}`")
    lines.append(f"Final grades: `{result['viva']['grades']}`")
    if result.get("learner_id") != learner.id:
        raise RuntimeError("Session did not resolve to the pre-seeded learner row")
    if taught_mastered:
        raise RuntimeError(f"Resume re-taught already-mastered concepts: {taught_mastered}")
    if "discover" in stages_seen or "assess" in stages_seen:
        raise RuntimeError("Returning learner was pushed through onboarding again")
    lines.append("Verified: resolved to her row, skipped mastered concepts, no re-onboarding.")

    progress = db.get_progress(learner.id)
    lines.append(f"Concept mastery rows after visit: `{progress['concepts']}`")

    out_dir = Path(__file__).resolve().parent.parent.parent / "docs" / "transcripts"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"returning_session_{language}.md"
    out_path.write_text("\n\n".join(lines), encoding="utf-8")
    print(f"Wrote {out_path}")
    print(f"Stages walked: {' -> '.join(stages_seen)}")


async def main(language: str) -> None:
    script = SCRIPT[language]
    package = store.load_skill("tailoring")

    db.init_db()
    # A failed earlier run may have left its learner behind; a second row
    # with the same PIN makes the PIN-first lookup ambiguous. Purge first.
    with db.get_db_session() as s:
        stale = [r.id for r in s.exec(select(db.Learner).where(db.Learner.name == "Sunita")).all()]
    for stale_id in stale:
        db.delete_learner(stale_id)
        print(f"Purged stale scripted learner {stale_id}")

    learner = db.create_learner(
        name="Sunita",
        village="Rampur",
        language=language,
        pin=PIN,
        interest_skill="tailoring",
        starting_level="some",
        notes="measured well last visit",
        consent_given_at=datetime.now(timezone.utc),
    )
    for concept_id in MASTERED:
        db.upsert_concept_mastery(learner.id, concept_id, "strong")

    try:
        await drive(language, script, package, learner)
    finally:
        db.delete_learner(learner.id)
        print(f"Cleaned up learner {learner.id}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "hi-IN"))
