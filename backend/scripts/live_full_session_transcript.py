"""Drives ONE FULL plan-v2 session against the real LLM -- greet -> discover
-> assess -> confirm_profile -> teach -> viva -> (forced) reteach -> earn ->
wrapup -> close -- and saves a markdown transcript to docs/transcripts/.

The driver is reactive, not a fixed answer list: teach length depends on what
the live diagnosis marks as gaps, and viva/reteach answers are looked up from
the rubric itself -- answering with a `sounds_right` exemplar normally, and
deliberately answering ONE question (fabric grain) with a `sounds_confused`
exemplar to force a real reteach round.

Usage: uv run python scripts/live_full_session_transcript.py [hi-IN|gu-IN]
Cleans up the learner row it creates.
"""

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

# Windows consoles default to cp1252, which can't print Devanagari/Gujarati.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from langgraph.checkpoint.memory import InMemorySaver  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agent.graph import compile_graph  # noqa: E402
from app.agent.state import initial_state  # noqa: E402
from app.content import store  # noqa: E402
from app.models import db  # noqa: E402

MAX_TURNS = 60
FAIL_CONCEPT = "c-grain"  # deliberately flub this one's first viva question

ONBOARDING = {
    "hi-IN": {
        "name_consent": "Mera naam Sunita hai, haan aap mujhe yaad rakh sakti hain",
        "village": "Main Rampur gaon se hoon, ghar par kheti ka kaam karti hoon",
        "skill": "tailoring",
        "stories": [
            "Haan, maine ek baar apni beti ke liye salwar silai thi, haath se",
            "Naap lena mujhe thoda aata hai, meri maa ne sikhaya tha inch tape se",
            "Machine kabhi nahi chalayi, aur kapda kaise kaatna hai yeh bhi nahi seekha",
        ],
        "confirm": "Haan, yeh sahi hai",
        "filler": "haan theek hai",
        "continue": "haan, aage badhiye",
        "teach_question": "yeh jo aapne bataya, thoda aur samjhao na, mujhe theek se samajh nahi aaya",
        "earn_more": "haan, batao kaun kharidega",
    },
    "gu-IN": {
        "name_consent": "Maru naam Sunita che, haa tame mane yaad rakhi shako",
        "village": "Hu Rampur gaam thi chu, ghare kheti nu kaam karu chu",
        "skill": "tailoring",
        "stories": [
            "Haa, mein ek vaar mari dikri mate salwar sidhyu hatu, haath thi",
            "Maap leta mane thodu aavde che, mari maa e shikhvadyu hatu",
            "Machine kadi nathi chalavi, ane kapdu kevi rite kaapvu e pan nathi shikhi",
        ],
        "confirm": "Haa, aa saachu che",
        "filler": "haa saru",
        "continue": "haa, aagal vadho",
        "teach_question": "aa je tame kahyu, thodu vadhare samjhavo ne",
        "earn_more": "haa, kaho kon kharidse",
    },
}


def pick_rubric_answer(result: dict, package: store.SkillPackage, failed_once: set[str]) -> str:
    """Answer the last-asked rubric question from its own exemplars: confused
    for FAIL_CONCEPT's first hearing, right otherwise."""
    asked = result["viva"]["question_ids_asked"]
    question = next(q for q in package.rubrics.questions if q.question_id == asked[-1])
    if question.concept_id == FAIL_CONCEPT and FAIL_CONCEPT not in failed_once:
        failed_once.add(FAIL_CONCEPT)
        return question.sounds_confused[0]
    return question.sounds_right[0]


async def main(language: str) -> None:
    script = ONBOARDING[language]
    package = store.load_skill("tailoring")

    db.init_db()
    session = db.create_session(learner_id=None, language=language)
    graph = compile_graph(InMemorySaver())
    config = {"configurable": {"thread_id": session.id}}

    lines = [
        f"# Full plan-v2 session transcript -- {language}",
        f"Recorded: {datetime.now(timezone.utc).isoformat()}",
        f"Deliberately-flubbed concept: `{FAIL_CONCEPT}` (forces a live reteach)",
        "",
    ]
    stages_seen: list[str] = []
    failed_once: set[str] = set()
    asked_teach_question = False

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
            answer = script["name_consent"]
        elif stage == "discover":
            answer = {0: script["filler"], 1: script["village"], 2: script["skill"]}[step]
        elif stage == "assess":
            answer = script["filler"] if step == 0 else script["stories"][(step - 1) % 3]
        elif stage == "confirm_profile":
            answer = script["filler"] if step == 0 else script["confirm"]
        elif stage == "teach":
            if step == 0:
                answer = script["filler"]
            elif not asked_teach_question and result["step_index"] == 0:
                asked_teach_question = True
                answer = script["teach_question"]
            else:
                answer = script["continue"]
        elif stage in ("viva", "reteach"):
            answer = (
                script["filler"]
                if step == 0
                else pick_rubric_answer(result, package, failed_once)
            )
        elif stage == "earn":
            answer = script["filler"] if step == 0 else script["earn_more"]
        elif stage == "wrapup":
            answer = script["filler"]
        else:  # resume or anything unexpected
            answer = script["filler"]

        lines.append(f"**Her:** {answer}")
        print(f"Her: {answer}")
        result = await graph.ainvoke({"transcript": answer}, config=config)
        log_mentor(result)
    else:
        raise RuntimeError(f"Session did not reach close within {MAX_TURNS} turns")

    # ---- verification against the database ---------------------------------
    learner_id = result.get("learner_id")
    lines += ["", "---", "", f"Stages walked: `{' -> '.join(stages_seen)}`"]
    lines.append(f"Learning path (gaps diagnosed live): `{result.get('learning_path')}`")
    lines.append(f"Final grades: `{result['viva']['grades']}`")
    lines.append(f"Reteach rounds: `{result.get('reteach_counts')}`")

    if learner_id:
        progress = db.get_progress(learner_id)
        lines.append(f"Lesson progress rows: `{progress['lessons']}`")
        lines.append(f"Concept mastery rows: `{progress['concepts']}`")
        db.delete_learner(learner_id)
        lines.append("Learner row deleted after verification (cleanup).")
        print(f"\nVerified + cleaned up learner {learner_id}")

    out_dir = Path(__file__).resolve().parent.parent.parent / "docs" / "transcripts"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"full_session_{language}.md"
    out_path.write_text("\n\n".join(lines), encoding="utf-8")
    print(f"Wrote {out_path}")
    print(f"Stages walked: {' -> '.join(stages_seen)}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "hi-IN"))
