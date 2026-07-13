"""CLI for the slow-lane Content Builder (plan v2).

Usage (from backend/):
    uv run python scripts/build_skill.py "mehndi"
    uv run python scripts/build_skill.py "pickle making" --skill-id pickle-making

Builds content/store/<skill_id>/ from real YouTube tutorial transcripts when
YOUTUBE_API_KEY is set (ungrounded otherwise), validates it, and prints a
review summary. Builder output starts trusted=false -- review the JSON, then
flip "trusted": true in curriculum.json.
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402
from app.content import builder, store  # noqa: E402


async def main() -> None:
    parser = argparse.ArgumentParser(description="Build a skill package into the content store")
    parser.add_argument("skill_name", help='e.g. "mehndi" or "pickle making"')
    parser.add_argument("--skill-id", default=None, help="store directory name (default: slugified name)")
    parser.add_argument("--force", action="store_true", help="rebuild even if the skill exists")
    args = parser.parse_args()

    skill_id = args.skill_id or builder.slugify(args.skill_name)
    if store.has_skill(skill_id) and not args.force:
        print(f"'{skill_id}' already exists in {store.store_root()}; use --force to rebuild.")
        return

    settings = get_settings()
    print(f"Building '{skill_id}' ({args.skill_name})...")
    if not settings.youtube_api_key:
        print("  (no YOUTUBE_API_KEY set: distilling ungrounded)")

    package = await builder.build_skill(
        skill_id, args.skill_name, youtube_api_key=settings.youtube_api_key
    )

    c = package.curriculum
    print(f"\nSaved to {store.store_root() / skill_id}")
    print(f"  grounded in videos : {c.source_video_ids or '(none)'}")
    print(f"  concepts           : {len(c.concepts)} ({sum(x.must_land for x in c.concepts)} must-land)")
    print(f"  steps              : {len(c.steps)}")
    print(f"  viva questions     : {len(package.rubrics.questions)}")
    print(f"  trusted            : {c.trusted}  <- review the JSON, then set true")


if __name__ == "__main__":
    asyncio.run(main())
