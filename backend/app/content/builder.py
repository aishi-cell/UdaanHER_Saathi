"""Slow lane: the Content Builder (plan v2, docs/app_plan_v2.md).

Turns a skill request into a cached, grounded SkillPackage:

    skill request
      -> YouTube Data API search (needs YOUTUBE_API_KEY; optional)
      -> transcripts via youtube-transcript-api (skip videos without)
      -> one structured LLM distill call -> SkillPackage shape
      -> save to content/store/<skill_id>/  (trusted=False until reviewed)

Never runs on the live conversation hot path: YouTube search is capped at
~100 calls/day (see plan v2 feasibility) and the whole build takes tens of
seconds. Discover triggers it in the background for unseeded skills.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Literal

import httpx
from pydantic import BaseModel, Field

from app.content import store
from app.services.llm import get_chat_model

logger = logging.getLogger(__name__)

YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
MAX_VIDEOS = 4
MAX_TRANSCRIPT_CHARS = 6000  # per video, keeps the distill prompt bounded


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return slug or "skill"


# ---------------------------------------------------------------------------
# Sourcing
# ---------------------------------------------------------------------------


async def search_videos(skill_name: str, *, api_key: str, max_results: int = MAX_VIDEOS) -> list[dict]:
    """YouTube Data API search for beginner tutorials, Hindi-first.
    Returns [{"video_id", "title"}]. Quota: 100 units/call, ~100 calls/day --
    batched offline use only."""
    params = {
        "part": "snippet",
        "type": "video",
        "maxResults": max_results,
        "relevanceLanguage": "hi",
        "safeSearch": "strict",
        "q": f"{skill_name} tutorial for beginners hindi",
        "key": api_key,
    }
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(YOUTUBE_SEARCH_URL, params=params)
    response.raise_for_status()
    return [
        {"video_id": item["id"]["videoId"], "title": item["snippet"]["title"]}
        for item in response.json().get("items", [])
        if item.get("id", {}).get("videoId")
    ]


def _fetch_transcript_sync(video_id: str) -> str | None:
    # Lazy import: keeps the dependency off the hot path and out of unit tests.
    from youtube_transcript_api import YouTubeTranscriptApi

    try:
        fetched = YouTubeTranscriptApi().fetch(
            video_id, languages=["hi", "gu", "en", "en-IN", "hi-Latn"]
        )
    except Exception as exc:  # no captions / disabled / throttled -> skip video
        logger.info("builder: no transcript for %s (%s)", video_id, exc)
        return None
    text = " ".join(snippet.text for snippet in fetched)
    return text[:MAX_TRANSCRIPT_CHARS] if text.strip() else None


async def fetch_transcript(video_id: str) -> str | None:
    return await asyncio.to_thread(_fetch_transcript_sync, video_id)


# ---------------------------------------------------------------------------
# Distilling (LLM structured output -> the store shape)
# ---------------------------------------------------------------------------


class GenText(BaseModel):
    en_in: str = Field(description="English text")
    hi_in: str = Field(description="Hindi text, Devanagari")
    gu_in: str = Field(description="Gujarati text, Gujarati script")

    def to_lang_text(self) -> dict[str, str]:
        return {"en-IN": self.en_in, "hi-IN": self.hi_in, "gu-IN": self.gu_in}


class GenConcept(BaseModel):
    concept_id: str = Field(description="kebab-case id starting with 'c-'")
    label: GenText
    must_land: bool
    best_video_id: str | None = Field(
        default=None,
        description=(
            "Of the transcript video ids provided, the ONE whose tutorial "
            "best shows this concept visually; null if none really does or "
            "no transcripts were given"
        ),
    )


class GenStep(BaseModel):
    concept_id: str
    teaching_notes: str = Field(
        description=(
            "English instructions FOR THE MENTOR LLM, not learner-facing text: "
            "what to convey in this 30-90 second spoken beat, what to "
            "emphasise, what mistake to warn about"
        )
    )
    caption: GenText = Field(description="One short line naming the step")


class GenQuestion(BaseModel):
    concept_id: str
    question: str = Field(description="Friendly conversational question, English, never test-like")
    sounds_right: list[str] = Field(
        description=(
            "2-3 examples of a CORRECT answer as a non-literate learner would "
            "speak it: informal, code-mixed romanized Hindi, incomplete but right"
        )
    )
    sounds_confused: list[str] = Field(
        description="1-2 common-misconception answers in the same spoken style"
    )


class GenEarning(BaseModel):
    products: list[str] = Field(description="3-4 things she can make/offer that actually sell locally")
    pricing_notes: str = Field(description="Realistic rupee ranges and what drives them, for the LLM")
    customer_notes: str = Field(description="Who buys, where to find them, how the first customers come")


class GenPackage(BaseModel):
    title: GenText
    concepts: list[GenConcept] = Field(description="4-6 concepts; mark the 3-4 essential ones must_land")
    steps: list[GenStep] = Field(description="6-10 ordered spoken micro-steps covering every concept")
    common_mistakes: list[str]
    earning: GenEarning
    questions: list[GenQuestion] = Field(
        description="2 questions per must_land concept, at least 1 for every other concept"
    )


DISTILL_SYSTEM = """You are building a spoken micro-curriculum for a voice-only mentor app \
that teaches low-literacy rural Indian women how to EARN from a vocational skill.

Skill: {skill_name}

{grounding}

Requirements:
- The learner cannot read. Every step must work as SPOKEN explanation alone.
- Order steps the way a patient local teacher would: basics first, earning-relevant technique next.
- teaching_notes are instructions for another LLM that will narrate them warmly \
in the learner's language -- write what to convey and what mistakes to warn about, not a script.
- The earning section is the point of the app: concrete products, realistic rupee amounts, \
real local customer channels (neighbours, local shops, self-help groups, melas).
- Never phrase questions like an exam; they are friendly chat. Avoid the words test/exam/score/wrong.
- Keep it safe: nothing requiring dangerous equipment without a safety note.
"""

GROUNDED_BLOCK = """Ground everything in these real tutorial transcripts (auto-captions, may be \
noisy -- extract the technique, ignore filler and channel promotion). Do not invent techniques \
that contradict them:

{transcripts}"""

UNGROUNDED_BLOCK = """No tutorial transcripts are available for this skill. Build the curriculum \
from well-established, widely-taught basics only -- be conservative, prefer what every teacher \
of this skill would agree on, and avoid anything niche or risky."""


async def distill(
    skill_id: str, skill_name: str, transcripts: dict[str, str]
) -> store.SkillPackage:
    if transcripts:
        blocks = "\n\n".join(
            f"--- transcript of video {vid} ---\n{text}" for vid, text in transcripts.items()
        )
        grounding = GROUNDED_BLOCK.format(transcripts=blocks)
    else:
        grounding = UNGROUNDED_BLOCK

    llm = get_chat_model(temperature=0.3).with_structured_output(GenPackage)
    generated: GenPackage = await llm.ainvoke(
        [
            {"role": "system", "content": DISTILL_SYSTEM.format(skill_name=skill_name, grounding=grounding)},
            {"role": "user", "content": f"Build the {skill_name} package now."},
        ]
    )

    curriculum = store.SkillCurriculum(
        skill_id=skill_id,
        title=generated.title.to_lang_text(),
        concepts=[
            store.Concept(
                concept_id=c.concept_id, label=c.label.to_lang_text(), must_land=c.must_land
            )
            for c in generated.concepts
        ],
        steps=[
            store.MicroStep(
                step_index=i,
                concept_id=s.concept_id,
                teaching_notes=s.teaching_notes,
                caption=s.caption.to_lang_text(),
            )
            for i, s in enumerate(generated.steps)
        ],
        common_mistakes=generated.common_mistakes,
        earning=store.EarningNotes(
            products=generated.earning.products,
            pricing_notes=generated.earning.pricing_notes,
            customer_notes=generated.earning.customer_notes,
        ),
        source_video_ids=list(transcripts.keys()),
        trusted=False,  # a human flips this after review (plan v2 open decision 4)
    )
    rubrics = store.SkillRubrics(
        skill_id=skill_id,
        questions=[
            store.RubricQuestion(
                question_id=f"q-{skill_id}-{i}",
                concept_id=q.concept_id,
                question=q.question,
                sounds_right=q.sounds_right,
                sounds_confused=q.sounds_confused,
            )
            for i, q in enumerate(generated.questions)
        ],
    )
    # Real tutorial clips per concept (user report: no visual tutorials were
    # ever shown): the distiller names which source video best demonstrates
    # each concept; teach/reteach offer it as an optional aid.
    aids = [
        store.VisualAid(
            concept_id=c.concept_id,
            kind="video",
            url_or_path=f"https://www.youtube.com/embed/{c.best_video_id}",
            note="source tutorial for this concept",
        )
        for c in generated.concepts
        if c.best_video_id and c.best_video_id in transcripts
    ]
    return store.SkillPackage(curriculum=curriculum, rubrics=rubrics, visual_aids=aids)


# ---------------------------------------------------------------------------
# The pipeline + background trigger
# ---------------------------------------------------------------------------


async def build_skill(
    skill_id: str, skill_name: str, *, youtube_api_key: str | None = None
) -> store.SkillPackage:
    """Full slow-lane build: search -> transcripts -> distill -> save."""
    transcripts: dict[str, str] = {}
    if youtube_api_key:
        try:
            videos = await search_videos(skill_name, api_key=youtube_api_key)
        except Exception as exc:
            logger.warning("builder: YouTube search failed for %r (%s); distilling ungrounded", skill_name, exc)
            videos = []
        for video in videos:
            text = await fetch_transcript(video["video_id"])
            if text:
                transcripts[video["video_id"]] = text
    else:
        logger.info("builder: no YOUTUBE_API_KEY configured; distilling %r ungrounded", skill_name)

    package = await distill(skill_id, skill_name, transcripts)
    store.save_skill(package)
    # Round-trip through the validating loader so a bad generation fails here,
    # in the background build, never at teach time.
    return store.load_skill(skill_id)


_in_flight: set[str] = set()


def start_background_build(
    skill_id: str, skill_name: str, *, youtube_api_key: str | None = None
) -> Literal["started", "already_building", "already_built"]:
    """Fire-and-forget build used by discover for unseeded skills. Deduped so
    two learners asking for the same skill build it once."""
    if store.package_exists(skill_id):
        return "already_built"
    if skill_id in _in_flight:
        return "already_building"

    _in_flight.add(skill_id)

    async def _run() -> None:
        try:
            await build_skill(skill_id, skill_name, youtube_api_key=youtube_api_key)
            logger.info("builder: background build of %r finished", skill_id)
        except Exception:
            logger.exception("builder: background build of %r failed", skill_id)
        finally:
            _in_flight.discard(skill_id)

    asyncio.get_running_loop().create_task(_run())
    return "started"
