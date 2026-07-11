"""Drives one full onboarding conversation (greet -> discover -> assess ->
confirm_profile -> teach) against the real LLM and saves a markdown
transcript to docs/transcripts/ for prompt review (T12 DoD).

Usage: uv run python scripts/live_onboarding_transcript.py <hi-IN|gu-IN>
"""

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

from langgraph.checkpoint.memory import InMemorySaver

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agent.graph import compile_graph  # noqa: E402
from app.agent.state import initial_state  # noqa: E402
from app.models import db  # noqa: E402

SCRIPTED_ANSWERS = {
    "hi-IN": [
        "Mera naam Sunita hai, haan aap mujhe yaad rakh sakti hain",
        "haan theek hai",  # filler: reply to greet's soft transition
        "Main Rampur gaon se hoon, ghar par kheti ka kaam karti hoon",
        "tailoring",
        "Haan, maine ek baar apni beti ke liye salwar silai thi",
        "Nahi, machine se kabhi nahi chalaya, sirf haath se silai ki hai",
        "Haan, mujhe pata hai ki kapde ka naap kaise lete hain",
        "Haan, yeh sahi hai",  # assess step3's answer, triggers level extraction
        "haan",  # filler: reply to confirm_profile's readback lead-in
        "Haan, yeh sahi hai",  # confirms the profile -> saved -> teach
    ],
    "gu-IN": [
        "Maru naam Sunita che, haa tame mane yaad rakhi shako",
        "haa saru",  # filler: reply to greet's soft transition
        "Hu Rampur gaam thi chu, ghare kheti nu kaam karu chu",
        "tailoring",
        "Haa, mein ek vaar mari dikri mate salwar sidhyu hatu",
        "Na, machine thi kadi nathi chalavyu, ke fakt haath thi sidhyu che",
        "Haa, mane khabar che ke kapda nu maap kevi rite levay",
        "Haa, aa saachu che",  # assess step3's answer, triggers level extraction
        "haa",  # filler: reply to confirm_profile's readback lead-in
        "Haa, aa saachu che",  # confirms the profile -> saved -> teach
    ],
}


async def main(language: str) -> None:
    db.init_db()
    session = db.create_session(learner_id=None, language=language)

    graph = compile_graph(InMemorySaver())
    config = {"configurable": {"thread_id": session.id}}

    transcript_lines = [
        f"# Onboarding transcript -- {language}",
        f"Recorded: {datetime.now(timezone.utc).isoformat()}",
        "",
    ]

    state = initial_state(session_id=session.id, learner_id=None, language=language)
    result = await graph.ainvoke(state, config=config)
    transcript_lines.append(f"**Mentor:** {result['reply_text']}")
    print(f"[{result['stage']}/{result['stage_step']}] Mentor: {result['reply_text']}")

    for her_answer in SCRIPTED_ANSWERS[language]:
        transcript_lines.append(f"**Her:** {her_answer}")
        print(f"Her: {her_answer}")
        result = await graph.ainvoke({"transcript": her_answer}, config=config)
        transcript_lines.append(f"**Mentor:** {result['reply_text']}")
        print(f"[{result['stage']}/{result['stage_step']}] Mentor: {result['reply_text']}")
        if result["stage"] == "teach":
            break

    transcript_lines.append("")
    transcript_lines.append(f"Final stage: `{result['stage']}`")
    transcript_lines.append(f"Learner id: `{result.get('learner_id')}`")

    out_dir = Path(__file__).resolve().parent.parent.parent / "docs" / "transcripts"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"onboarding_{language}.md"
    out_path.write_text("\n\n".join(transcript_lines), encoding="utf-8")
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    lang = sys.argv[1] if len(sys.argv) > 1 else "hi-IN"
    asyncio.run(main(lang))
