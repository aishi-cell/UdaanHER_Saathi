"""Content store + builder tests (plan v2)."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.content import builder, store


@pytest.fixture
def tmp_store(tmp_path):
    store.configure_store_root(tmp_path)
    yield tmp_path
    store.configure_store_root(None)


def _minimal_package(skill_id: str = "candle-making") -> store.SkillPackage:
    return store.SkillPackage(
        curriculum=store.SkillCurriculum(
            skill_id=skill_id,
            title={"en-IN": "Candles", "hi-IN": "मोमबत्ती", "gu-IN": "મીણબત્તી"},
            concepts=[
                store.Concept(concept_id="c-wax", label={"en-IN": "Wax"}, must_land=True),
                store.Concept(concept_id="c-wick", label={"en-IN": "Wick"}),
            ],
            steps=[
                store.MicroStep(
                    step_index=0,
                    concept_id="c-wax",
                    teaching_notes="melt slowly",
                    caption={"en-IN": "Melt"},
                ),
                store.MicroStep(
                    step_index=1,
                    concept_id="c-wick",
                    teaching_notes="center the wick",
                    caption={"en-IN": "Wick"},
                ),
            ],
            earning=store.EarningNotes(
                products=["diya candles"], pricing_notes="Rs 10 each", customer_notes="melas"
            ),
        ),
        rubrics=store.SkillRubrics(
            skill_id=skill_id,
            questions=[
                store.RubricQuestion(
                    question_id="q1",
                    concept_id="c-wax",
                    question="why melt slowly?",
                    sounds_right=["dheere se, warna jal jaata hai"],
                    sounds_confused=["tez aanch pe"],
                ),
                store.RubricQuestion(
                    question_id="q2",
                    concept_id="c-wick",
                    question="where does the wick go?",
                    sounds_right=["beech mein"],
                    sounds_confused=["kahin bhi"],
                ),
            ],
        ),
        visual_aids=[],
    )


# --- the seeded skill ------------------------------------------------------


def test_seeded_tailoring_package_is_valid():
    package = store.load_skill("tailoring")
    assert package.curriculum.trusted is True
    assert len(package.curriculum.concepts) >= 4
    assert any(c.must_land for c in package.curriculum.concepts)
    assert package.curriculum.earning.products
    # every concept has at least one viva question (enforced by _cross_check,
    # asserted here as documentation)
    for concept in package.curriculum.concepts:
        assert package.questions_for_concept(concept.concept_id)


def test_validate_all_includes_tailoring():
    assert "tailoring" in store.validate_all()


def test_skill_cards_come_from_the_store():
    cards = store.skill_cards("hi-IN")
    tailoring = next(c for c in cards if c["id"] == "tailoring")
    assert tailoring["label"] == "सिलाई"


# --- save/load round trip + validation -------------------------------------


def test_save_and_load_round_trip(tmp_store):
    saved = _minimal_package()
    store.save_skill(saved)
    assert store.package_exists("candle-making")
    loaded = store.load_skill("candle-making")
    assert loaded.curriculum.title["hi-IN"] == "मोमबत्ती"
    assert [q.question_id for q in loaded.rubrics.questions] == ["q1", "q2"]


def test_corrupt_json_fails_loud_naming_the_file(tmp_store):
    store.save_skill(_minimal_package())
    path = tmp_store / "candle-making" / "curriculum.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(store.ContentError, match="curriculum.json"):
        store.validate_all()


def test_missing_field_fails_loud_naming_the_field(tmp_store):
    store.save_skill(_minimal_package())
    path = tmp_store / "candle-making" / "curriculum.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    del data["earning"]
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(store.ContentError, match="earning"):
        store.load_skill("candle-making")


def test_step_with_unknown_concept_fails_cross_check(tmp_store):
    package = _minimal_package()
    package.curriculum.steps[0].concept_id = "c-nonexistent"
    store.save_skill(package)
    with pytest.raises(store.ContentError, match="c-nonexistent"):
        store.load_skill("candle-making")


def test_concept_without_viva_question_fails_cross_check(tmp_store):
    package = _minimal_package()
    package.rubrics.questions = package.rubrics.questions[:1]  # drop c-wick's
    store.save_skill(package)
    with pytest.raises(store.ContentError, match="c-wick"):
        store.load_skill("candle-making")


# --- language fallback -------------------------------------------------------


def test_pick_language_exact_then_base_then_english_then_any():
    text = {"en-IN": "hello", "hi-IN": "namaste"}
    assert store.pick_language(text, "hi-IN") == "namaste"
    assert store.pick_language({"hi": "namaste", "en-IN": "hello"}, "hi-IN") == "namaste"
    assert store.pick_language(text, "gu-IN") == "hello"
    assert store.pick_language({"mr-IN": "namaskar"}, "gu-IN") == "namaskar"
    assert store.pick_language({}, "gu-IN") == ""


def test_aids_prefer_session_language_then_hindi():
    package = _minimal_package()
    package.visual_aids = [
        store.VisualAid(concept_id="c-wax", kind="video", url_or_path="u-hi", language="hi-IN"),
        store.VisualAid(concept_id="c-wax", kind="video", url_or_path="u-gu", language="gu-IN"),
        store.VisualAid(concept_id="c-wax", kind="diagram", url_or_path="u-any", language="any"),
    ]
    ranked = package.aids_for_concept("c-wax", "gu-IN")
    assert [a.url_or_path for a in ranked] == ["u-gu", "u-hi", "u-any"]


# --- builder -----------------------------------------------------------------


def test_slugify():
    assert builder.slugify("Pickle Making!") == "pickle-making"
    assert builder.slugify("  mehndi  ") == "mehndi"


def _gen_package() -> builder.GenPackage:
    text = builder.GenText(en_in="Candles", hi_in="मोमबत्ती", gu_in="મીણબત્તી")
    return builder.GenPackage(
        title=text,
        concepts=[builder.GenConcept(concept_id="c-wax", label=text, must_land=True)],
        steps=[builder.GenStep(concept_id="c-wax", teaching_notes="melt slowly", caption=text)],
        common_mistakes=["overheating"],
        earning=builder.GenEarning(
            products=["diyas"], pricing_notes="Rs 10", customer_notes="melas"
        ),
        questions=[
            builder.GenQuestion(
                concept_id="c-wax",
                question="why slow?",
                sounds_right=["dheere"],
                sounds_confused=["tez"],
            )
        ],
    )


@pytest.mark.asyncio
async def test_build_skill_distills_saves_and_revalidates(tmp_store):
    fake_llm = MagicMock()
    fake_llm.with_structured_output.return_value.ainvoke = AsyncMock(return_value=_gen_package())

    with patch("app.content.builder.get_chat_model", return_value=fake_llm):
        package = await builder.build_skill("candle-making", "candle making")

    assert store.package_exists("candle-making")
    # human review flips trusted -- until then the build exists but is NOT
    # offered or teachable (a live session once showed an unreviewed card)
    assert package.curriculum.trusted is False
    assert store.has_skill("candle-making") is False
    assert "candle-making" not in store.list_skills()
    assert package.curriculum.title["gu-IN"] == "મીણબત્તી"
    assert package.rubrics.questions[0].concept_id == "c-wax"
    # no YOUTUBE_API_KEY passed -> ungrounded, no provenance
    assert package.curriculum.source_video_ids == []


@pytest.mark.asyncio
async def test_background_build_dedupes(tmp_store):
    fake_llm = MagicMock()
    fake_llm.with_structured_output.return_value.ainvoke = AsyncMock(return_value=_gen_package())

    with patch("app.content.builder.get_chat_model", return_value=fake_llm):
        first = builder.start_background_build("candle-making", "candle making")
        second = builder.start_background_build("candle-making", "candle making")
        # let the background task finish
        import asyncio

        for _ in range(50):
            if store.package_exists("candle-making"):
                break
            await asyncio.sleep(0.05)

    assert first == "started"
    assert second == "already_building"
    assert store.package_exists("candle-making")
    assert builder.start_background_build("candle-making", "candle making") == "already_built"


# --- SVG sanitizer -------------------------------------------------------------


def test_svg_sanitizer_allows_internal_refs_blocks_external():
    from app.content.visuals import _sanitize

    ok = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300">'
        '<line marker-end="url(#arrow)"/><use href="#a"/></svg>'
    )
    assert _sanitize(ok) is not None
    assert _sanitize('<svg><image href="http://evil"/></svg>') is None
    assert _sanitize('<svg><rect fill="url(http://evil)"/></svg>') is None
    assert _sanitize("<svg><script>alert(1)</script></svg>") is None
    assert _sanitize("<svg><a href=http://evil>x</a></svg>") is None
    assert _sanitize("no svg here") is None
