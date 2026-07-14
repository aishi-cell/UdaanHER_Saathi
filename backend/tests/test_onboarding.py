from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.agent.nodes import assess, confirm_profile, discover, greet, resume
from app.agent.nodes.assess import DiagnosticExtraction
from app.agent.nodes.confirm_profile import ConfirmationExtraction
from app.agent.nodes.discover import SkillChoiceExtraction, VillageWorkExtraction
from app.agent.nodes.greet import ConsentExtraction, GreetExtraction, PinExtraction
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
async def test_greet_step1_new_visitor_gets_consent_question():
    state = make_state(
        stage="greet", stage_step=1, transcript="Mera naam Sunita hai, pehli baar aayi hoon"
    )

    with (
        patch(
            "app.agent.nodes.greet.extract_structured",
            new=AsyncMock(return_value=GreetExtraction(name="Sunita", returning=False)),
        ) as mock_extract,
        patch(
            "app.agent.nodes.greet.ask_conversational",
            new=AsyncMock(return_value="Yaad rakhun aapko?"),
        ),
    ):
        result = await greet.run(state)

    assert result["stage"] == "greet"
    assert result["stage_step"] == 2
    assert result["profile"] == {"name": "Sunita"}
    assert mock_extract.call_args.kwargs["schema"] is GreetExtraction


@pytest.mark.asyncio
async def test_greet_step1_returning_visitor_gets_pin_question():
    state = make_state(stage="greet", stage_step=1, transcript="Meena, haan pehle aayi thi")

    with (
        patch(
            "app.agent.nodes.greet.extract_structured",
            new=AsyncMock(return_value=GreetExtraction(name="Meena", returning=True)),
        ),
        patch(
            "app.agent.nodes.greet.ask_conversational",
            new=AsyncMock(return_value="Apna PIN boliye"),
        ),
    ):
        result = await greet.run(state)

    assert result["stage"] == "greet"
    assert result["stage_step"] == 3
    assert result["profile"] == {"name": "Meena"}


@pytest.mark.asyncio
async def test_greet_step2_consent_yes_advances_to_discover():
    state = make_state(
        stage="greet", stage_step=2, profile={"name": "Sunita"}, transcript="haan, yaad rakho"
    )

    with (
        patch(
            "app.agent.nodes.greet.extract_structured",
            new=AsyncMock(return_value=ConsentExtraction(consent_given=True)),
        ) as mock_extract,
        patch(
            "app.agent.nodes.greet.ask_conversational",
            new=AsyncMock(return_value="Shukriya Sunita!"),
        ),
    ):
        result = await greet.run(state)

    assert result["stage"] == "discover"
    assert result["stage_step"] == 0
    assert result["consent_declined"] is False
    assert mock_extract.call_args.kwargs["schema"] is ConsentExtraction


@pytest.mark.asyncio
async def test_greet_consent_declined_sets_flag():
    state = make_state(
        stage="greet", stage_step=2, profile={"name": "Sunita"}, transcript="nahi"
    )

    with (
        patch(
            "app.agent.nodes.greet.extract_structured",
            new=AsyncMock(return_value=ConsentExtraction(consent_given=False)),
        ),
        patch("app.agent.nodes.greet.ask_conversational", new=AsyncMock(return_value="Theek hai")),
    ):
        result = await greet.run(state)

    assert result["stage"] == "discover"
    assert result["consent_declined"] is True


def _returning_learner(pin: str = "4271", interest: str | None = "tailoring"):
    return db.create_learner(
        name="Meena",
        village="Rampur",
        language="hi-IN",
        pin=pin,
        interest_skill=interest,
        starting_level="some",
        notes="was measuring well",
        consent_given_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_greet_pin_match_resumes_at_her_gaps():
    learner = _returning_learner()
    db.upsert_concept_mastery(learner.id, "c-tape-basics", "strong")
    db.upsert_concept_mastery(learner.id, "c-measure-points", "shaky")
    session = db.create_session(learner_id=None, language="hi-IN")
    state = make_state(
        session_id=session.id,
        stage="greet",
        stage_step=3,
        profile={"name": "Meena"},
        transcript="chaar do saat ek",
    )

    with (
        patch(
            "app.agent.nodes.greet.extract_structured",
            new=AsyncMock(return_value=PinExtraction(pin="4271")),
        ),
        patch(
            "app.agent.nodes.greet.ask_conversational",
            new=AsyncMock(return_value="Wapas swagat, Meena!"),
        ),
    ):
        result = await greet.run(state)

    assert result["stage"] == "teach"
    assert result["stage_step"] == 0
    assert result["learner_id"] == learner.id
    assert result["skill_id"] == "tailoring"
    assert result["profile"]["interest"] == "tailoring"
    assert result["consent_declined"] is False
    # Her path skips what she already mastered, keeps the shaky + untouched.
    assert "c-tape-basics" not in result["learning_path"]
    assert "c-measure-points" in result["learning_path"]
    with db.get_db_session() as s:
        assert s.get(db.Session, session.id).learner_id == learner.id


@pytest.mark.asyncio
async def test_greet_pin_match_survives_cross_script_name():
    """Live-run bug: stored name 'Sunita' (Latin), extracted name 'सुनीता'
    (Devanagari). The PIN is the secret; the name must not lock her out."""
    learner = _returning_learner(pin="4271")
    session = db.create_session(learner_id=None, language="hi-IN")
    state = make_state(
        session_id=session.id,
        stage="greet",
        stage_step=3,
        profile={"name": "मीना"},  # different script than the stored 'Meena'
        transcript="chaar do saat ek",
    )

    with (
        patch(
            "app.agent.nodes.greet.extract_structured",
            new=AsyncMock(return_value=PinExtraction(pin="४२७१")),  # Devanagari digits too
        ),
        patch(
            "app.agent.nodes.greet.ask_conversational",
            new=AsyncMock(return_value="Wapas swagat!"),
        ),
    ):
        result = await greet.run(state)

    assert result["stage"] == "teach"
    assert result["learner_id"] == learner.id


def test_find_learner_by_pin_name_breaks_ties():
    a = _returning_learner(pin="4271")
    b = db.create_learner(
        name="Radha",
        village=None,
        language="hi-IN",
        pin="4271",
        interest_skill=None,
        starting_level=None,
        notes=None,
        consent_given_at=datetime.now(timezone.utc),
    )

    assert db.find_learner_by_pin("4271", name_hint="meena").id == a.id
    assert db.find_learner_by_pin("4271", name_hint="RADHA").id == b.id
    # Shared PIN and an unrecognisable name: refuse rather than guess.
    assert db.find_learner_by_pin("4271", name_hint="कोई और") is None
    assert db.find_learner_by_pin("9999", name_hint="meena") is None


@pytest.mark.asyncio
async def test_greet_pin_extraction_tolerates_noise_around_digits():
    learner = _returning_learner(pin="4271")
    session = db.create_session(learner_id=None, language="hi-IN")
    state = make_state(
        session_id=session.id,
        stage="greet",
        stage_step=3,
        profile={"name": "Meena"},
        transcript="mera pin 4-2-7-1 hai",
    )

    with (
        patch(
            "app.agent.nodes.greet.extract_structured",
            new=AsyncMock(return_value=PinExtraction(pin="4-2-7-1")),
        ),
        patch(
            "app.agent.nodes.greet.ask_conversational",
            new=AsyncMock(return_value="Wapas swagat!"),
        ),
    ):
        result = await greet.run(state)

    assert result["stage"] == "teach"
    assert result["learner_id"] == learner.id


@pytest.mark.asyncio
async def test_greet_pin_miss_retries_once_then_starts_fresh():
    _returning_learner(pin="4271")
    wrong = PinExtraction(pin="9999")

    # First miss (step 3): one gentle retry.
    state = make_state(
        stage="greet", stage_step=3, profile={"name": "Meena"}, transcript="nau nau nau nau"
    )
    with (
        patch("app.agent.nodes.greet.extract_structured", new=AsyncMock(return_value=wrong)),
        patch(
            "app.agent.nodes.greet.ask_conversational", new=AsyncMock(return_value="Phir se?")
        ),
    ):
        result = await greet.run(state)
    assert result["stage"] == "greet"
    assert result["stage_step"] == 4

    # Second miss (step 4): start fresh -- back to the consent question.
    state = make_state(
        stage="greet", stage_step=4, profile={"name": "Meena"}, transcript="nau nau nau nau"
    )
    with (
        patch("app.agent.nodes.greet.extract_structured", new=AsyncMock(return_value=wrong)),
        patch(
            "app.agent.nodes.greet.ask_conversational",
            new=AsyncMock(return_value="Koi baat nahi, naye se shuru karte hain."),
        ),
    ):
        result = await greet.run(state)
    assert result["stage"] == "greet"
    assert result["stage_step"] == 2


@pytest.mark.asyncio
async def test_greet_pin_unclear_reasks_same_step():
    state = make_state(stage="greet", stage_step=3, profile={"name": "Meena"}, transcript=" ")

    with (
        patch("app.agent.nodes.greet.extract_structured", new=AsyncMock()) as mock_extract,
        patch(
            "app.agent.nodes.greet.ask_conversational", new=AsyncMock(return_value="Phir se?")
        ),
    ):
        result = await greet.run(state)

    mock_extract.assert_not_awaited()
    assert result["stage"] == "greet"
    assert result["stage_step"] == 3


# --- resume (T22) ----------------------------------------------------------


@pytest.mark.asyncio
async def test_resume_node_builds_gap_path_and_welcomes_back():
    learner = _returning_learner()
    db.upsert_concept_mastery(learner.id, "c-tape-basics", "strong")
    state = make_state(
        stage="resume",
        learner_id=learner.id,
        skill_id="tailoring",
        profile={"name": "Meena", "interest": "tailoring"},
    )

    with patch(
        "app.agent.nodes.resume.ask_conversational",
        new=AsyncMock(return_value="Wapas swagat, Meena!"),
    ) as mock_ask:
        result = await resume.run(state)

    assert result["stage"] == "teach"
    assert result["stage_step"] == 0
    assert "c-tape-basics" not in result["learning_path"]
    assert len(result["learning_path"]) == 5
    assert result["reply_text"] == "Wapas swagat, Meena!"
    assert "Meena" in mock_ask.call_args.kwargs["instruction"]


@pytest.mark.asyncio
async def test_resume_all_strong_gives_must_land_refresh():
    learner = _returning_learner()
    for concept_id in [
        "c-tape-basics",
        "c-measure-points",
        "c-tape-tension",
        "c-grain",
        "c-seam-allowance",
        "c-straight-seam",
    ]:
        db.upsert_concept_mastery(learner.id, concept_id, "strong")
    state = make_state(
        stage="resume",
        learner_id=learner.id,
        skill_id="tailoring",
        profile={"name": "Meena", "interest": "tailoring"},
    )

    with patch(
        "app.agent.nodes.resume.ask_conversational",
        new=AsyncMock(return_value="Wapas swagat!"),
    ):
        result = await resume.run(state)

    # Finished everything -> a short refresh of the must-land concepts,
    # never an empty session.
    assert result["learning_path"] == [
        "c-measure-points",
        "c-tape-tension",
        "c-grain",
        "c-seam-allowance",
    ]


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
async def test_confirm_profile_speaks_her_pin_on_save():
    import re

    profile = {"name": "Sunita", "village": "Rampur", "interest": "tailoring"}
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
            new=AsyncMock(return_value="Chaliye shuru karein!"),
        ),
    ):
        result = await confirm_profile.run(state)

    # The PIN sentence is appended by code, never left to the LLM (a live
    # session once ended with no PIN ever spoken), and the card shows it too.
    spoken = re.search(r"(\d) (\d) (\d) (\d)", result["reply_text"])
    assert spoken, f"PIN digits not spoken in: {result['reply_text']}"
    pin = "".join(spoken.groups())
    assert result["ui"]["type"] == "show_profile_card"
    assert result["ui"]["profile"]["pin"] == pin
    # The digits she hears must be the digits that actually unlock her row.
    found = db.get_learner_by_name_pin("Sunita", pin)
    assert found is not None
    assert found.id == result["learner_id"]


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


# --- choose_language (voice-first language pick) ----------------------------


@pytest.mark.asyncio
async def test_choose_language_step0_speaks_prompt_with_cards():
    from app.agent.nodes import choose_language

    state = make_state(stage="choose_language", stage_step=0, language="hi-IN", transcript="")
    result = await choose_language.run(state)

    assert result["stage"] == "choose_language"
    assert result["stage_step"] == 1
    assert result["ui"]["type"] == "show_options"
    assert {o["id"] for o in result["ui"]["options"]} == {"hi-IN", "gu-IN", "en-IN"}


@pytest.mark.parametrize(
    ("spoken", "expected"),
    [
        ("mujhe hindi aati hai", "hi-IN"),
        ("હું ગુજરાતી બોલું છું", "gu-IN"),
        ("English please", "en-IN"),
        ("gu-IN", "gu-IN"),  # a tapped card arrives as the bare id
    ],
)
@pytest.mark.asyncio
async def test_choose_language_sets_language_and_greets_in_same_turn(spoken, expected):
    from app.agent.nodes import choose_language

    state = make_state(stage="choose_language", stage_step=1, language="hi-IN", transcript=spoken)
    with patch(
        "app.agent.nodes.greet.ask_conversational", new=AsyncMock(return_value="Namaste!")
    ) as mock_ask:
        result = await choose_language.run(state)

    assert result["language"] == expected
    assert result["stage"] == "greet"
    assert result["stage_step"] == 1
    assert mock_ask.call_args.kwargs["language"] == expected


@pytest.mark.asyncio
async def test_choose_language_reasks_on_unrecognised_answer():
    from app.agent.nodes import choose_language

    state = make_state(
        stage="choose_language", stage_step=1, language="hi-IN", transcript="kuch bhi"
    )
    result = await choose_language.run(state)

    assert result["stage"] == "choose_language"
    assert result["stage_step"] == 1
    assert result["ui"]["type"] == "show_options"
