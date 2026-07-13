from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.agent.nodes import assess, confirm_profile, discover, greet
from app.agent.nodes.assess import DiagnosticExtraction
from app.agent.nodes.confirm_profile import ConfirmationExtraction
from app.agent.nodes.discover import SkillChoiceExtraction, VillageWorkExtraction
from app.agent.nodes.greet import GreetExtraction
from app.agent.state import initial_state
from app.models import db


@pytest.fixture(autouse=True)
def temp_db(tmp_path):
    db.configure_engine(f"sqlite:///{tmp_path / 'test.db'}")
    db.init_db()
    yield
    db._engine = None


def make_state(**overrides):
    state = initial_state(session_id="s1", learner_id=None, language="hi-IN")
    state.update(overrides)
    return state


# --- greet ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_greet_step0_asks_and_stays_in_greet():
    state = make_state(stage="greet", stage_step=0, transcript="")

    with patch(
        "app.agent.nodes.greet.ask_conversational", new=AsyncMock(return_value="Namaste!")
    ) as mock_ask:
        result = await greet.run(state)

    assert result["stage"] == "greet"
    assert result["stage_step"] == 1
    assert result["reply_text"] == "Namaste!"
    mock_ask.assert_awaited_once()
    assert mock_ask.call_args.kwargs["language"] == "hi-IN"


@pytest.mark.asyncio
async def test_greet_step1_extracts_name_and_consent_and_advances():
    state = make_state(stage="greet", stage_step=1, transcript="Mera naam Sunita hai, haan")

    with (
        patch(
            "app.agent.nodes.greet.extract_structured",
            new=AsyncMock(return_value=GreetExtraction(name="Sunita", consent_given=True)),
        ) as mock_extract,
        patch(
            "app.agent.nodes.greet.ask_conversational", new=AsyncMock(return_value="Shukriya Sunita!")
        ),
    ):
        result = await greet.run(state)

    assert result["stage"] == "discover"
    assert result["stage_step"] == 0
    assert result["profile"] == {"name": "Sunita"}
    assert result["consent_declined"] is False
    assert mock_extract.call_args.kwargs["schema"] is GreetExtraction


@pytest.mark.asyncio
async def test_greet_consent_declined_sets_flag():
    state = make_state(stage="greet", stage_step=1, transcript="Sunita, nahi")

    with (
        patch(
            "app.agent.nodes.greet.extract_structured",
            new=AsyncMock(return_value=GreetExtraction(name="Sunita", consent_given=False)),
        ),
        patch("app.agent.nodes.greet.ask_conversational", new=AsyncMock(return_value="Theek hai")),
    ):
        result = await greet.run(state)

    assert result["consent_declined"] is True


# --- discover --------------------------------------------------------------


@pytest.mark.asyncio
async def test_discover_step0_asks_village_and_work():
    state = make_state(stage="discover", stage_step=0, profile={"name": "Sunita"})

    with patch(
        "app.agent.nodes.discover.ask_conversational", new=AsyncMock(return_value="Kaunse gaon se?")
    ):
        result = await discover.run(state)

    assert result["stage"] == "discover"
    assert result["stage_step"] == 1


@pytest.mark.asyncio
async def test_discover_step1_extracts_village_and_shows_interest_options():
    state = make_state(
        stage="discover", stage_step=1, profile={"name": "Sunita"}, transcript="Rampur se hoon"
    )

    with (
        patch(
            "app.agent.nodes.discover.extract_structured",
            new=AsyncMock(
                return_value=VillageWorkExtraction(village="Rampur", work_notes="farming")
            ),
        ),
        patch(
            "app.agent.nodes.discover.ask_conversational",
            new=AsyncMock(return_value="Kaunsa hunar seekhna hai?"),
        ),
    ):
        result = await discover.run(state)

    assert result["stage"] == "discover"
    assert result["stage_step"] == 2
    assert result["profile"]["village"] == "Rampur"
    assert result["ui"]["type"] == "show_options"
    # Cards come from the content store now (plan v2) -- whatever is seeded.
    assert len(result["ui"]["options"]) >= 1
    assert {opt["id"] for opt in result["ui"]["options"]} >= {"tailoring"}


@pytest.mark.asyncio
async def test_discover_step2_tap_skips_extraction():
    state = make_state(
        stage="discover",
        stage_step=2,
        profile={"name": "Sunita", "village": "Rampur"},
        transcript="tailoring",
    )

    with (
        patch("app.agent.nodes.discover.extract_structured", new=AsyncMock()) as mock_extract,
        patch("app.agent.nodes.discover.ask_conversational", new=AsyncMock(return_value="Accha!")),
    ):
        result = await discover.run(state)

    mock_extract.assert_not_awaited()
    assert result["stage"] == "assess"
    assert result["profile"]["interest"] == "tailoring"


@pytest.mark.asyncio
async def test_discover_step2_voice_uses_extraction():
    state = make_state(
        stage="discover",
        stage_step=2,
        profile={"name": "Sunita", "village": "Rampur"},
        transcript="mujhe tailoring seekhni hai",
    )

    with (
        patch(
            "app.agent.nodes.discover.extract_structured",
            new=AsyncMock(
                return_value=SkillChoiceExtraction(
                    matched_skill_id="tailoring", skill_name_english="tailoring"
                )
            ),
        ) as mock_extract,
        patch("app.agent.nodes.discover.ask_conversational", new=AsyncMock(return_value="Accha!")),
    ):
        result = await discover.run(state)

    mock_extract.assert_awaited_once()
    assert result["profile"]["interest"] == "tailoring"


# --- assess ------------------------------------------------------------


@pytest.mark.asyncio
async def test_assess_asks_three_questions_before_extracting():
    profile = {"name": "Sunita", "interest": "tailoring"}

    for step in range(assess.MAX_QUESTIONS):
        state = make_state(stage="assess", stage_step=step, profile=profile, transcript="haan")
        with patch(
            "app.agent.nodes.assess.ask_conversational", new=AsyncMock(return_value=f"Q{step}")
        ):
            result = await assess.run(state)
        assert result["stage"] == "assess"
        assert result["stage_step"] == step + 1


@pytest.mark.asyncio
async def test_assess_final_step_extracts_level_and_advances():
    profile = {"name": "Sunita", "interest": "tailoring"}
    state = make_state(
        stage="assess",
        stage_step=assess.MAX_QUESTIONS,
        profile=profile,
        transcript="haan maine kabhi kapde silai kiye hain",
        history=[{"role": "mentor", "text": "Q1"}],
    )

    with (
        patch(
            "app.agent.nodes.assess.extract_structured",
            new=AsyncMock(
                return_value=DiagnosticExtraction(
                    starting_level="some", notes="has some experience", concept_estimates=[]
                )
            ),
        ),
        patch("app.agent.nodes.assess.ask_conversational", new=AsyncMock(return_value="Shukriya!")),
    ):
        result = await assess.run(state)

    assert result["stage"] == "confirm_profile"
    assert result["profile"]["starting_level"] == "some"
    assert result["profile"]["notes"] == "has some experience"


# --- confirm_profile -----------------------------------------------------


@pytest.mark.asyncio
async def test_confirm_profile_step0_reads_back_and_shows_card():
    profile = {"name": "Sunita", "village": "Rampur", "interest": "tailoring"}
    state = make_state(stage="confirm_profile", stage_step=0, profile=profile)

    with patch(
        "app.agent.nodes.confirm_profile.ask_conversational",
        new=AsyncMock(return_value="Yeh sahi hai?"),
    ):
        result = await confirm_profile.run(state)

    assert result["stage"] == "confirm_profile"
    assert result["stage_step"] == 1
    assert result["ui"]["type"] == "show_profile_card"
    assert result["ui"]["profile"]["name"] == "Sunita"


@pytest.mark.asyncio
async def test_confirm_profile_saves_learner_on_yes():
    profile = {
        "name": "Sunita",
        "village": "Rampur",
        "interest": "tailoring",
        "starting_level": "some",
        "notes": "some experience",
    }
    session = db.create_session(learner_id=None, language="hi-IN")
    state = make_state(
        session_id=session.id,
        stage="confirm_profile",
        stage_step=1,
        profile=profile,
        transcript="haan sahi hai",
        consent_declined=False,
    )

    with (
        patch(
            "app.agent.nodes.confirm_profile.extract_structured",
            new=AsyncMock(return_value=ConfirmationExtraction(confirmed=True)),
        ),
        patch(
            "app.agent.nodes.confirm_profile.ask_conversational",
            new=AsyncMock(return_value="Chaliye shuru karte hain!"),
        ),
    ):
        result = await confirm_profile.run(state)

    assert result["stage"] == "teach"
    assert result["learner_id"] is not None

    with db.get_db_session() as s:
        learner = s.get(db.Learner, result["learner_id"])
        assert learner is not None
        assert learner.name == "Sunita"
        assert learner.consent_given_at is not None

        session_row = s.get(db.Session, session.id)
        assert session_row.learner_id == result["learner_id"]


@pytest.mark.asyncio
async def test_confirm_profile_consent_declined_never_saves():
    profile = {"name": "Sunita", "village": "Rampur", "interest": "tailoring"}
    session = db.create_session(learner_id=None, language="hi-IN")
    state = make_state(
        session_id=session.id,
        stage="confirm_profile",
        stage_step=1,
        profile=profile,
        transcript="haan sahi hai",
        consent_declined=True,
    )

    with (
        patch(
            "app.agent.nodes.confirm_profile.extract_structured",
            new=AsyncMock(return_value=ConfirmationExtraction(confirmed=True)),
        ),
        patch(
            "app.agent.nodes.confirm_profile.ask_conversational",
            new=AsyncMock(return_value="Chaliye shuru karte hain!"),
        ),
    ):
        result = await confirm_profile.run(state)

    assert result["stage"] == "teach"
    assert result["learner_id"] is None

    with db.get_db_session() as s:
        from sqlmodel import select

        assert s.exec(select(db.Learner)).all() == []


@pytest.mark.asyncio
async def test_confirm_profile_correction_loops_back():
    profile = {"name": "Sunita", "village": "Rampur", "interest": "tailoring"}
    state = make_state(
        stage="confirm_profile", stage_step=1, profile=profile, transcript="nahi, gaon Devpur hai"
    )

    with (
        patch(
            "app.agent.nodes.confirm_profile.extract_structured",
            new=AsyncMock(
                return_value=ConfirmationExtraction(
                    confirmed=False, corrected_field="village", corrected_value="Devpur"
                )
            ),
        ),
        patch(
            "app.agent.nodes.confirm_profile.ask_conversational",
            new=AsyncMock(return_value="Devpur, samjh gayi!"),
        ),
    ):
        result = await confirm_profile.run(state)

    assert result["stage"] == "confirm_profile"
    assert result["stage_step"] == 0
    assert result["profile"]["village"] == "Devpur"


def test_consent_given_at_recorded():
    session = db.create_session(learner_id=None, language="hi-IN")
    before = datetime.now(timezone.utc)
    learner = db.create_learner(
        name="Test",
        village=None,
        language="hi-IN",
        pin="1234",
        interest_skill="tailoring",
        starting_level="some",
        notes=None,
        consent_given_at=before,
    )
    assert learner.consent_given_at is not None
    db.link_session_to_learner(session.id, learner.id)
    with db.get_db_session() as s:
        session_row = s.get(db.Session, session.id)
        assert session_row.learner_id == learner.id


# --- unclear/incomplete speech handling -----------------------------------
# Sarvam's transcript can be empty or near-empty for a low-literacy speaker's
# mumbled, cut-off, or heavily accented answer. Every real extraction point
# must re-ask instead of pushing garbage through structured extraction.


@pytest.mark.parametrize("bad_transcript", ["", " ", "a", "  h  "])
@pytest.mark.asyncio
async def test_greet_reasks_on_unclear_answer_instead_of_extracting(bad_transcript):
    state = make_state(stage="greet", stage_step=1, transcript=bad_transcript)

    with (
        patch("app.agent.nodes.greet.extract_structured", new=AsyncMock()) as mock_extract,
        patch(
            "app.agent.nodes.greet.ask_conversational", new=AsyncMock(return_value="Sorry, again?")
        ),
    ):
        result = await greet.run(state)

    mock_extract.assert_not_awaited()
    assert result["stage"] == "greet"
    assert result["stage_step"] == 1


@pytest.mark.asyncio
async def test_discover_village_reasks_on_unclear_answer():
    state = make_state(
        stage="discover", stage_step=1, profile={"name": "Sunita"}, transcript="  "
    )

    with (
        patch("app.agent.nodes.discover.extract_structured", new=AsyncMock()) as mock_extract,
        patch(
            "app.agent.nodes.discover.ask_conversational", new=AsyncMock(return_value="Again?")
        ),
    ):
        result = await discover.run(state)

    mock_extract.assert_not_awaited()
    assert result["stage"] == "discover"
    assert result["stage_step"] == 1


@pytest.mark.asyncio
async def test_discover_interest_reasks_on_unclear_voice_answer():
    state = make_state(
        stage="discover",
        stage_step=2,
        profile={"name": "Sunita", "village": "Rampur"},
        transcript="m",
    )

    with (
        patch("app.agent.nodes.discover.extract_structured", new=AsyncMock()) as mock_extract,
        patch(
            "app.agent.nodes.discover.ask_conversational", new=AsyncMock(return_value="Again?")
        ),
    ):
        result = await discover.run(state)

    mock_extract.assert_not_awaited()
    assert result["stage"] == "discover"
    assert result["stage_step"] == 2


@pytest.mark.asyncio
async def test_assess_reasks_same_question_on_unclear_answer():
    profile = {"name": "Sunita", "interest": "tailoring"}
    state = make_state(stage="assess", stage_step=2, profile=profile, transcript="")

    with patch(
        "app.agent.nodes.assess.ask_conversational", new=AsyncMock(return_value="Again?")
    ) as mock_ask:
        result = await assess.run(state)

    assert result["stage"] == "assess"
    assert result["stage_step"] == 2  # unchanged -- same question repeats
    assert mock_ask.call_args.kwargs["instruction"] == assess.REASK_INSTRUCTION


@pytest.mark.asyncio
async def test_confirm_profile_reasks_on_unclear_answer_without_saving():
    profile = {"name": "Sunita", "village": "Rampur", "interest": "tailoring"}
    state = make_state(stage="confirm_profile", stage_step=1, profile=profile, transcript="")

    with (
        patch("app.agent.nodes.confirm_profile.extract_structured", new=AsyncMock()) as mock_extract,
        patch(
            "app.agent.nodes.confirm_profile.ask_conversational",
            new=AsyncMock(return_value="Again?"),
        ),
    ):
        result = await confirm_profile.run(state)

    mock_extract.assert_not_awaited()
    assert result["stage"] == "confirm_profile"
    assert result["stage_step"] == 1
    assert result["ui"]["type"] == "show_profile_card"
