"""Plan-v2 teaching-loop tests: assess diagnosis -> personalized path ->
teach -> viva -> reteach -> earn -> wrapup, all with mocked LLMs against the
seeded tailoring package."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.agent.nodes import assess, earn, reteach, teach, viva, wrapup
from app.agent.nodes.assess import ConceptEstimate, DiagnosticExtraction
from app.agent.nodes.teach import TeachIntent
from app.agent.nodes.viva import VivaGrade
from app.agent.state import initial_state
from app.content import store
from app.models import db

PROFILE = {"name": "Sunita", "interest": "tailoring", "starting_level": "some"}


@pytest.fixture(autouse=True)
def temp_db(tmp_path):
    db.configure_engine(f"sqlite:///{tmp_path / 'test.db'}")
    db.init_db()
    yield
    db._engine = None


def make_state(**overrides):
    state = initial_state(
        session_id="s1",
        learner_id=None,
        language="hi-IN",
        profile=PROFILE,
        skill_id="tailoring",
    )
    state.update(overrides)
    return state


def _package() -> store.SkillPackage:
    return store.load_skill("tailoring")


# --- assess: diagnosis -> learning path -------------------------------------


@pytest.mark.asyncio
async def test_assess_builds_gap_only_learning_path():
    estimates = [
        ConceptEstimate(concept_id="c-tape-basics", estimate="knows"),
        ConceptEstimate(concept_id="c-measure-points", estimate="knows"),
        ConceptEstimate(concept_id="c-tape-tension", estimate="gap"),
        ConceptEstimate(concept_id="c-grain", estimate="gap"),
        ConceptEstimate(concept_id="c-seam-allowance", estimate="gap"),
        ConceptEstimate(concept_id="c-straight-seam", estimate="knows"),
    ]
    state = make_state(stage="assess", stage_step=assess.MAX_QUESTIONS, transcript="...kahani...")

    with (
        patch(
            "app.agent.nodes.assess.extract_structured",
            new=AsyncMock(
                return_value=DiagnosticExtraction(
                    starting_level="some", notes="sews at home", concept_estimates=estimates
                )
            ),
        ),
        patch("app.agent.nodes.assess.ask_conversational", new=AsyncMock(return_value="ok")),
    ):
        result = await assess.run(state)

    # gaps only, in curriculum order -- what she knows is skipped
    assert result["learning_path"] == ["c-tape-tension", "c-grain", "c-seam-allowance"]
    assert result["concept_estimates"]["c-tape-basics"] == "knows"
    assert result["stage"] == "confirm_profile"


@pytest.mark.asyncio
async def test_assess_all_known_falls_back_to_must_land_refresh():
    estimates = [
        ConceptEstimate(concept_id=c.concept_id, estimate="knows")
        for c in _package().curriculum.concepts
    ]
    state = make_state(stage="assess", stage_step=assess.MAX_QUESTIONS, transcript="...")

    with (
        patch(
            "app.agent.nodes.assess.extract_structured",
            new=AsyncMock(
                return_value=DiagnosticExtraction(
                    starting_level="experienced", notes="", concept_estimates=estimates
                )
            ),
        ),
        patch("app.agent.nodes.assess.ask_conversational", new=AsyncMock(return_value="ok")),
    ):
        result = await assess.run(state)

    must_land = [c.concept_id for c in _package().curriculum.concepts if c.must_land]
    assert result["learning_path"] == must_land


# --- teach: personalized step walk ------------------------------------------


@pytest.mark.asyncio
async def test_teach_entry_narrates_first_path_step_only():
    state = make_state(stage="teach", stage_step=0, learning_path=["c-grain"])

    with patch("app.agent.nodes.teach.ask_conversational", new=AsyncMock(return_value="ok")):
        result = await teach.run(state)

    assert result["stage"] == "teach"
    assert result["ui"]["type"] == "show_lesson_step"
    # her path has exactly the two c-grain steps -- not the full curriculum
    assert result["ui"]["total_steps"] == 2
    assert result["step_index"] == 0


@pytest.mark.asyncio
async def test_teach_continue_advances_and_last_step_lands_in_viva():
    state = make_state(
        stage="teach", stage_step=1, step_index=0, learning_path=["c-grain"], transcript="haan aage"
    )

    with (
        patch(
            "app.agent.nodes.teach.extract_structured",
            new=AsyncMock(return_value=TeachIntent(intent="continue")),
        ),
        patch("app.agent.nodes.teach.ask_conversational", new=AsyncMock(return_value="ok")),
    ):
        result = await teach.run(state)
        assert result["stage"] == "teach"
        assert result["step_index"] == 1  # advanced to the second c-grain step

        state2 = make_state(
            stage="teach",
            stage_step=1,
            step_index=1,
            learning_path=["c-grain"],
            transcript="haan",
        )
        result2 = await teach.run(state2)

    assert result2["stage"] == "viva"


@pytest.mark.asyncio
async def test_teach_question_holds_the_step():
    state = make_state(
        stage="teach",
        stage_step=1,
        step_index=0,
        learning_path=["c-grain"],
        transcript="yeh selvedge kya hota hai?",
    )

    with (
        patch(
            "app.agent.nodes.teach.extract_structured",
            new=AsyncMock(return_value=TeachIntent(intent="question")),
        ),
        patch("app.agent.nodes.teach.ask_conversational", new=AsyncMock(return_value="ok")),
    ):
        result = await teach.run(state)

    assert result["stage"] == "teach"
    assert result["step_index"] == 0  # held


@pytest.mark.asyncio
async def test_teach_stop_goes_to_wrapup():
    state = make_state(
        stage="teach", stage_step=1, step_index=0, learning_path=["c-grain"], transcript="bas aaj"
    )

    with (
        patch(
            "app.agent.nodes.teach.extract_structured",
            new=AsyncMock(return_value=TeachIntent(intent="stop")),
        ),
        patch("app.agent.nodes.teach.ask_conversational", new=AsyncMock(return_value="ok")),
    ):
        result = await teach.run(state)

    assert result["stage"] == "wrapup"


@pytest.mark.asyncio
async def test_teach_marks_lesson_in_progress_for_consented_learner():
    learner = db.create_learner(
        name="Sunita", village=None, language="hi-IN", pin="1234",
        interest_skill="tailoring", starting_level="some", notes=None,
        consent_given_at=datetime.now(timezone.utc),
    )
    state = make_state(stage="teach", stage_step=0, learner_id=learner.id, learning_path=["c-grain"])

    with patch("app.agent.nodes.teach.ask_conversational", new=AsyncMock(return_value="ok")):
        await teach.run(state)

    progress = db.get_progress(learner.id)
    assert any(entry["lesson_id"] == "tailoring" for entry in progress["lessons"])


# --- viva: rubric questions, grading, code-computed routing ------------------


@pytest.mark.asyncio
async def test_viva_asks_must_land_concepts_first():
    state = make_state(
        stage="viva", stage_step=0, learning_path=["c-tape-basics", "c-grain"], transcript=""
    )

    with patch("app.agent.nodes.viva.ask_conversational", new=AsyncMock(return_value="ok")):
        result = await viva.run(state)

    asked = result["viva"]["question_ids_asked"]
    assert len(asked) == 1
    question = next(q for q in _package().rubrics.questions if q.question_id == asked[0])
    assert question.concept_id == "c-grain"  # must_land beats curriculum order


@pytest.mark.asyncio
async def test_viva_all_strong_routes_to_earn_and_writes_mastery():
    learner = db.create_learner(
        name="Sunita", village=None, language="hi-IN", pin="1234",
        interest_skill="tailoring", starting_level="some", notes=None,
        consent_given_at=datetime.now(timezone.utc),
    )
    package = _package()
    grain_q = package.questions_for_concept("c-grain")[0]
    state = make_state(
        stage="viva",
        stage_step=1,
        learner_id=learner.id,
        learning_path=["c-grain"],
        viva={"question_ids_asked": [grain_q.question_id], "grades": {}},
        transcript="disha ke hisaab se kaatna hai warna tedha latakta hai",
    )

    with (
        patch(
            "app.agent.nodes.viva.extract_structured",
            new=AsyncMock(return_value=VivaGrade(grade="strong", one_line_reason="got it")),
        ),
        patch("app.agent.nodes.viva.ask_conversational", new=AsyncMock(return_value="ok")),
    ):
        result = await viva.run(state)

    assert result["stage"] == "earn"
    assert result["viva"]["grades"] == {"c-grain": "strong"}
    progress = db.get_progress(learner.id)
    grain = next(c for c in progress["concepts"] if c["concept_id"] == "c-grain")
    assert grain["mastery"] == "strong"


@pytest.mark.asyncio
async def test_viva_shaky_routes_to_reteach():
    package = _package()
    grain_q = package.questions_for_concept("c-grain")[0]
    state = make_state(
        stage="viva",
        stage_step=1,
        learning_path=["c-grain"],
        viva={"question_ids_asked": [grain_q.question_id], "grades": {}},
        transcript="koi farak nahi padta kaise bhi kaato",
    )

    with (
        patch(
            "app.agent.nodes.viva.extract_structured",
            new=AsyncMock(return_value=VivaGrade(grade="shaky", one_line_reason="confused")),
        ),
        patch("app.agent.nodes.viva.ask_conversational", new=AsyncMock(return_value="ok")),
    ):
        result = await viva.run(state)

    assert result["stage"] == "reteach"
    assert result["viva"]["grades"]["c-grain"] == "shaky"


# --- reteach: different explanation, fresh question, 2-round cap -------------


@pytest.mark.asyncio
async def test_reteach_explains_with_fresh_question_and_counts_the_round():
    package = _package()
    first_q = package.questions_for_concept("c-grain")[0]
    state = make_state(
        stage="reteach",
        stage_step=0,
        learning_path=["c-grain"],
        viva={"question_ids_asked": [first_q.question_id], "grades": {"c-grain": "shaky"}},
        transcript="",
    )

    with (
        patch("app.agent.nodes.reteach.ask_conversational", new=AsyncMock(return_value="ok")),
        patch(
            "app.agent.nodes.reteach.visuals.generate_diagram",
            new=AsyncMock(return_value="data:image/svg+xml;base64,AAAA"),
        ),
    ):
        result = await reteach.run(state)

    assert result["stage"] == "reteach"
    assert result["reteach_counts"] == {"c-grain": 1}
    # re-check uses a question she has NOT heard yet
    new_q = result["viva"]["question_ids_asked"][-1]
    assert new_q != first_q.question_id
    assert package.rubrics.questions and any(q.question_id == new_q for q in package.rubrics.questions)
    # no vetted aid in the seed store -> generated diagram shown
    assert result["ui"]["type"] == "show_lesson_step"
    assert result["ui"]["image"].startswith("data:image/svg+xml")


@pytest.mark.asyncio
async def test_reteach_degrades_to_voice_when_diagram_generation_fails():
    state = make_state(
        stage="reteach",
        stage_step=0,
        learning_path=["c-grain"],
        viva={"question_ids_asked": [], "grades": {"c-grain": "shaky"}},
        transcript="",
    )

    with (
        patch("app.agent.nodes.reteach.ask_conversational", new=AsyncMock(return_value="ok")),
        patch(
            "app.agent.nodes.reteach.visuals.generate_diagram", new=AsyncMock(return_value=None)
        ),
    ):
        result = await reteach.run(state)

    assert result["stage"] == "reteach"
    assert result["ui"]["type"] == "idle"  # voice must stand alone


@pytest.mark.asyncio
async def test_reteach_cap_moves_on_to_earn_never_a_third_drill():
    state = make_state(
        stage="reteach",
        stage_step=0,
        learning_path=["c-grain"],
        viva={"question_ids_asked": [], "grades": {"c-grain": "shaky"}},
        reteach_counts={"c-grain": 2},
        transcript="",
    )

    with patch("app.agent.nodes.reteach.ask_conversational", new=AsyncMock(return_value="ok")):
        result = await reteach.run(state)

    assert result["stage"] == "earn"


@pytest.mark.asyncio
async def test_reteach_strong_recheck_moves_on():
    package = _package()
    asked = [q.question_id for q in package.questions_for_concept("c-grain")]
    state = make_state(
        stage="reteach",
        stage_step=1,
        learning_path=["c-grain"],
        viva={"question_ids_asked": asked, "grades": {"c-grain": "shaky"}},
        reteach_counts={"c-grain": 1},
        transcript="haan samajh gayi, disha dekh ke kaatna hai",
    )

    with (
        patch(
            "app.agent.nodes.reteach.extract_structured",
            new=AsyncMock(return_value=VivaGrade(grade="strong", one_line_reason="landed")),
        ),
        patch("app.agent.nodes.reteach.ask_conversational", new=AsyncMock(return_value="ok")),
    ):
        result = await reteach.run(state)

    assert result["stage"] == "earn"
    assert result["viva"]["grades"]["c-grain"] == "strong"


# --- earn + wrapup ------------------------------------------------------------


@pytest.mark.asyncio
async def test_earn_two_beats_then_wrapup():
    state = make_state(stage="earn", stage_step=0, transcript="")
    with patch("app.agent.nodes.earn.ask_conversational", new=AsyncMock(return_value="ok")) as ask:
        result = await earn.run(state)
        assert result["stage"] == "earn"
        assert "Rs 100-300" in ask.call_args.kwargs["instruction"]  # grounded rupee numbers

        state2 = make_state(stage="earn", stage_step=1, transcript="haan batao")
        result2 = await earn.run(state2)

    assert result2["stage"] == "wrapup"


@pytest.mark.asyncio
async def test_wrapup_completes_lesson_when_path_must_land_all_strong():
    learner = db.create_learner(
        name="Sunita", village=None, language="hi-IN", pin="1234",
        interest_skill="tailoring", starting_level="some", notes=None,
        consent_given_at=datetime.now(timezone.utc),
    )
    state = make_state(
        stage="wrapup",
        stage_step=0,
        learner_id=learner.id,
        learning_path=["c-grain", "c-tape-basics"],
        viva={
            "question_ids_asked": [],
            "grades": {"c-grain": "strong", "c-tape-basics": "strong"},
        },
        transcript="",
    )

    with patch("app.agent.nodes.wrapup.ask_conversational", new=AsyncMock(return_value="ok")):
        result = await wrapup.run(state)

    assert result["stage"] == "close"
    assert result["ui"]["type"] == "show_progress"
    progress = db.get_progress(learner.id)
    lesson = next(entry for entry in progress["lessons"] if entry["lesson_id"] == "tailoring")
    assert lesson["status"] == "done"


@pytest.mark.asyncio
async def test_wrapup_leaves_in_progress_when_a_must_land_is_shaky():
    learner = db.create_learner(
        name="Sunita", village=None, language="hi-IN", pin="1234",
        interest_skill="tailoring", starting_level="some", notes=None,
        consent_given_at=datetime.now(timezone.utc),
    )
    state = make_state(
        stage="wrapup",
        stage_step=0,
        learner_id=learner.id,
        learning_path=["c-grain"],
        viva={"question_ids_asked": [], "grades": {"c-grain": "shaky"}},
        transcript="",
    )

    with patch("app.agent.nodes.wrapup.ask_conversational", new=AsyncMock(return_value="ok")):
        result = await wrapup.run(state)

    progress = db.get_progress(learner.id)
    lesson = next(entry for entry in progress["lessons"] if entry["lesson_id"] == "tailoring")
    assert lesson["status"] == "current"  # in_progress -> "current" in the UI vocabulary
    assert result["stage"] == "close"


# --- consent: no learner row, no writes ---------------------------------------


@pytest.mark.asyncio
async def test_viva_never_writes_mastery_when_consent_declined():
    package = _package()
    grain_q = package.questions_for_concept("c-grain")[0]
    state = make_state(
        stage="viva",
        stage_step=1,
        learner_id="someone",  # even with an id, declined consent blocks writes
        consent_declined=True,
        learning_path=["c-grain"],
        viva={"question_ids_asked": [grain_q.question_id], "grades": {}},
        transcript="disha se kaato",
    )

    with (
        patch(
            "app.agent.nodes.viva.extract_structured",
            new=AsyncMock(return_value=VivaGrade(grade="strong", one_line_reason="ok")),
        ),
        patch("app.agent.nodes.viva.ask_conversational", new=AsyncMock(return_value="ok")),
        patch("app.agent.nodes.viva.db.upsert_concept_mastery") as mock_upsert,
    ):
        await viva.run(state)

    mock_upsert.assert_not_called()
