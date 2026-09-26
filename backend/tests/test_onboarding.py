from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.agent.nodes import assess, confirm_profile, discover, greet, resume
from app.agent.nodes.assess import DiagnosticExtraction
from app.agent.nodes.confirm_profile import ConfirmationExtraction
from app.agent.nodes.discover import SkillChoiceExtraction, VillageWorkExtraction
from app.agent.nodes.greet import ConsentExtraction, GreetExtraction, PinExtraction
from app.agent.nodes.resume import MilestoneCheckExtraction
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
    """Roadmap item 2: consenting and being asked where she's from happen
    in the same turn -- no throwaway round-trip in between."""
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
        patch(
            "app.agent.nodes.discover.ask_conversational",
            new=AsyncMock(return_value="Aap kis gaon se hain?"),
        ),
    ):
        result = await greet.run(state)

    assert result["stage"] == "discover"
    assert result["stage_step"] == 1  # discover's own opening step already ran
    assert result["consent_declined"] is False
    assert result["reply_text"] == "Shukriya Sunita! Aap kis gaon se hain?"
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
        patch(
            "app.agent.nodes.discover.ask_conversational",
            new=AsyncMock(return_value="Aap kis gaon se hain?"),
        ),
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
            "app.agent.nodes.resume.ask_conversational",
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
async def test_greet_pin_match_mentions_her_next_career_milestone():
    """The voice PIN path chains into resume.run() for its welcome-back
    reply, same as the typed/remembered-login path -- one implementation,
    so it gets the milestone mention for free."""
    _returning_learner()
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
            "app.agent.nodes.resume.ask_conversational", new=AsyncMock(return_value="ok")
        ) as mock_ask,
    ):
        await greet.run(state)

    instruction = mock_ask.call_args.kwargs["instruction"]
    assert "Started learning" in instruction  # nothing achieved yet -> first in catalog


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
            "app.agent.nodes.resume.ask_conversational",
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
            "app.agent.nodes.resume.ask_conversational",
            new=AsyncMock(return_value="Wapas swagat!"),
        ),
    ):
        result = await greet.run(state)

    assert result["stage"] == "teach"
    assert result["learner_id"] == learner.id


@pytest.mark.asyncio
async def test_greet_pin_miss_retries_up_to_max_then_starts_fresh():
    _returning_learner(pin="4271")
    wrong = PinExtraction(pin="9999")

    # Misses on steps 3..5 (attempts 1..3 of MAX_PIN_ATTEMPTS=4): each gets
    # a gentle retry with a keypad still on screen, and reports how many
    # tries remain.
    for step in range(greet.PIN_STEP_START, greet.PIN_STEP_START + greet.MAX_PIN_ATTEMPTS - 1):
        state = make_state(
            stage="greet", stage_step=step, profile={"name": "Meena"}, transcript="nau nau nau nau"
        )
        with (
            patch("app.agent.nodes.greet.extract_structured", new=AsyncMock(return_value=wrong)),
            patch(
                "app.agent.nodes.greet.ask_conversational", new=AsyncMock(return_value="Phir se?")
            ),
        ):
            result = await greet.run(state)
        assert result["stage"] == "greet"
        assert result["stage_step"] == step + 1
        assert result["ui"]["type"] == "request_pin"
        assert result["ui"]["attempt"] == step - greet.PIN_STEP_START + 2

    # Final miss (4th attempt): start fresh -- back to the consent question.
    final_step = greet.PIN_STEP_START + greet.MAX_PIN_ATTEMPTS - 1
    state = make_state(
        stage="greet", stage_step=final_step, profile={"name": "Meena"}, transcript="nau nau nau nau"
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
async def test_greet_pin_from_keypad_skips_llm_extraction():
    """A tapped keypad (or a clean 4-digit transcript) is unambiguous -- no
    need to pay for an LLM call to parse it (Phase 1: faster responses)."""
    learner = _returning_learner(pin="4271")
    session = db.create_session(learner_id=None, language="hi-IN")
    state = make_state(
        session_id=session.id,
        stage="greet",
        stage_step=greet.PIN_STEP_START,
        profile={"name": "Meena"},
        transcript="4271",
    )

    with (
        patch("app.agent.nodes.greet.extract_structured", new=AsyncMock()) as mock_extract,
        patch(
            "app.agent.nodes.resume.ask_conversational",
            new=AsyncMock(return_value="Wapas swagat!"),
        ),
    ):
        result = await greet.run(state)

    mock_extract.assert_not_awaited()
    assert result["stage"] == "teach"
    assert result["learner_id"] == learner.id


@pytest.mark.asyncio
async def test_greet_pin_step_shows_keypad_ui():
    state = make_state(stage="greet", stage_step=1, transcript="Meena, haan pehle aayi thi")

    with (
        patch(
            "app.agent.nodes.greet.extract_structured",
            new=AsyncMock(return_value=GreetExtraction(name="Meena", returning=True)),
        ),
        patch(
            "app.agent.nodes.greet.ask_conversational",
            new=AsyncMock(return_value="Apna PIN boliye ya dabaiye"),
        ),
    ):
        result = await greet.run(state)

    assert result["ui"]["type"] == "request_pin"
    assert result["ui"]["attempt"] == 1
    assert result["ui"]["max_attempts"] == greet.MAX_PIN_ATTEMPTS


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
async def test_resume_mentions_her_next_career_milestone():
    """Career roadmap (roadmap item 3): "explain her current progress and
    the next milestone" -- the most natural moment is right when she
    returns."""
    learner = _returning_learner()
    db.mark_milestone(learner.id, "tailoring", "started_skill")
    state = make_state(
        stage="resume",
        learner_id=learner.id,
        skill_id="tailoring",
        profile={"name": "Meena", "interest": "tailoring"},
    )

    with patch(
        "app.agent.nodes.resume.ask_conversational", new=AsyncMock(return_value="ok")
    ) as mock_ask:
        await resume.run(state)

    instruction = mock_ask.call_args.kwargs["instruction"]
    assert "Made the first thing" in instruction  # the next unachieved one
    assert "Started learning" not in instruction  # already done, not "next"


def _learner_ready_for_milestone_check(pin: str = "4271") -> db.Learner:
    """A returning learner who's completed every auto-tracked milestone for
    tailoring -- her next one (found_customer) is self-reported, so resume
    should actively ask about it instead of just mentioning it in passing."""
    learner = _returning_learner(pin=pin)
    for m in ["started_skill", "made_product", "learned_pricing", "completed_skill"]:
        db.mark_milestone(learner.id, "tailoring", m)
    return learner


@pytest.mark.asyncio
async def test_resume_asks_about_self_reported_milestone_instead_of_mentioning_it():
    learner = _learner_ready_for_milestone_check()
    state = make_state(
        stage="resume",
        stage_step=0,
        learner_id=learner.id,
        skill_id="tailoring",
        profile={"name": "Meena", "interest": "tailoring"},
    )

    with patch(
        "app.agent.nodes.resume.ask_conversational", new=AsyncMock(return_value="ok")
    ) as mock_ask:
        result = await resume.run(state)

    # Held for her answer -- not handed off to teach yet.
    assert result["stage"] == "resume"
    assert result["stage_step"] == 1
    instruction = mock_ask.call_args.kwargs["instruction"]
    assert "first customer" in instruction


@pytest.mark.asyncio
async def test_resume_milestone_check_yes_marks_it_and_proceeds_to_teach():
    learner = _learner_ready_for_milestone_check()
    state = make_state(
        stage="resume",
        stage_step=1,
        learner_id=learner.id,
        skill_id="tailoring",
        profile={"name": "Meena", "interest": "tailoring"},
        transcript="haan, ek didi ne mujhse blouse silwaya",
    )

    with (
        patch(
            "app.agent.nodes.resume.extract_structured",
            new=AsyncMock(return_value=MilestoneCheckExtraction(achieved="yes")),
        ),
        patch(
            "app.agent.nodes.resume.ask_conversational", new=AsyncMock(return_value="ok")
        ) as mock_ask,
    ):
        result = await resume.run(state)

    assert result["stage"] == "teach"
    milestone_ids = {m.milestone_id for m in db.get_milestones(learner.id, skill_id="tailoring")}
    assert "found_customer" in milestone_ids
    assert "customer" in mock_ask.call_args.kwargs["instruction"].lower()


@pytest.mark.asyncio
async def test_resume_milestone_check_not_yet_does_not_mark_but_still_proceeds():
    learner = _learner_ready_for_milestone_check()
    state = make_state(
        stage="resume",
        stage_step=1,
        learner_id=learner.id,
        skill_id="tailoring",
        profile={"name": "Meena", "interest": "tailoring"},
        transcript="nahi abhi tak nahi mila",
    )

    with (
        patch(
            "app.agent.nodes.resume.extract_structured",
            new=AsyncMock(return_value=MilestoneCheckExtraction(achieved="not_yet")),
        ),
        patch("app.agent.nodes.resume.ask_conversational", new=AsyncMock(return_value="ok")),
    ):
        result = await resume.run(state)

    assert result["stage"] == "teach"  # no dead end, no pressure
    milestone_ids = {m.milestone_id for m in db.get_milestones(learner.id, skill_id="tailoring")}
    assert "found_customer" not in milestone_ids


@pytest.mark.asyncio
async def test_resume_milestone_check_unclear_answer_reasks():
    learner = _learner_ready_for_milestone_check()
    state = make_state(
        stage="resume",
        stage_step=1,
        learner_id=learner.id,
        skill_id="tailoring",
        profile={"name": "Meena", "interest": "tailoring"},
        transcript=" ",
    )

    with (
        patch("app.agent.nodes.resume.extract_structured", new=AsyncMock()) as mock_extract,
        patch("app.agent.nodes.resume.ask_conversational", new=AsyncMock(return_value="ok")),
    ):
        result = await resume.run(state)

    mock_extract.assert_not_awaited()  # too short to bother extracting
    assert result["stage"] == "resume"
    assert result["stage_step"] == 1


@pytest.mark.asyncio
async def test_resume_milestone_check_genuinely_ambiguous_extraction_reasks():
    learner = _learner_ready_for_milestone_check()
    state = make_state(
        stage="resume",
        stage_step=1,
        learner_id=learner.id,
        skill_id="tailoring",
        profile={"name": "Meena", "interest": "tailoring"},
        transcript="pata nahi kya bol rahi hoon",
    )

    with (
        patch(
            "app.agent.nodes.resume.extract_structured",
            new=AsyncMock(return_value=MilestoneCheckExtraction(achieved="unclear")),
        ),
        patch("app.agent.nodes.resume.ask_conversational", new=AsyncMock(return_value="ok")),
    ):
        result = await resume.run(state)

    assert result["stage"] == "resume"
    assert result["stage_step"] == 1
    milestone_ids = {m.milestone_id for m in db.get_milestones(learner.id, skill_id="tailoring")}
    assert "found_customer" not in milestone_ids


@pytest.mark.asyncio
async def test_greet_pin_match_chains_into_resume_milestone_check():
    """The voice PIN path shares resume.run() end to end now -- confirm the
    active milestone check-in reaches her there too, not just via the
    typed/remembered-login path."""
    learner = _learner_ready_for_milestone_check()
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
            "app.agent.nodes.resume.ask_conversational", new=AsyncMock(return_value="ok")
        ) as mock_ask,
    ):
        result = await greet.run(state)

    assert result["stage"] == "resume"
    assert result["stage_step"] == 1
    assert result["learner_id"] == learner.id
    assert "first customer" in mock_ask.call_args.kwargs["instruction"]


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
        patch(
            "app.agent.nodes.assess.ask_conversational",
            new=AsyncMock(return_value="Kya aapne kabhi kapde silai kiye hain?"),
        ),
    ):
        result = await discover.run(state)

    mock_extract.assert_not_awaited()
    # Roadmap item 2: the skill-choice ack and assess's first question land
    # in the same turn -- no throwaway round-trip in between.
    assert result["stage"] == "assess"
    assert result["profile"]["interest"] == "tailoring"
    assert result["reply_text"] == "Accha! Kya aapne kabhi kapde silai kiye hain?"


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
        patch(
            "app.agent.nodes.assess.ask_conversational",
            new=AsyncMock(return_value="Kya aapne kabhi kapde silai kiye hain?"),
        ),
    ):
        result = await discover.run(state)

    mock_extract.assert_awaited_once()
    assert result["profile"]["interest"] == "tailoring"


@pytest.mark.asyncio
async def test_discover_step2_implausible_skill_reasks_instead_of_building():
    """Bug found via a live full-session test: garbled/off-topic input
    reaching this step (e.g. a stray "nahi") once triggered a real
    background build that fabricated an entire fake curriculum out of
    nothing -- caught only by the trusted-gate, never by input validation.
    The model can flag this itself; use that instead of guessing a name."""
    state = make_state(
        stage="discover",
        stage_step=2,
        profile={"name": "Sunita", "village": "Rampur"},
        transcript="nahi",
    )

    with (
        patch(
            "app.agent.nodes.discover.extract_structured",
            new=AsyncMock(
                return_value=SkillChoiceExtraction(
                    matched_skill_id="", skill_name_english="", is_plausible_skill=False
                )
            ),
        ),
        patch("app.agent.nodes.discover.ask_conversational", new=AsyncMock(return_value="Phir se?")),
        patch("app.content.builder.start_background_build") as mock_build,
    ):
        result = await discover.run(state)

    mock_build.assert_not_called()
    assert result["stage"] == "discover"
    assert result["stage_step"] == 2
    assert result["ui"]["type"] == "show_options"


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
        patch(
            "app.agent.nodes.confirm_profile.ask_conversational",
            new=AsyncMock(return_value="Yeh sahi hai?"),
        ),
    ):
        result = await assess.run(state)

    # Roadmap item 2: the wrap-up and confirm_profile's readback+question
    # land in the same turn -- no throwaway round-trip in between.
    assert result["stage"] == "confirm_profile"
    assert result["profile"]["starting_level"] == "some"
    assert result["profile"]["notes"] == "has some experience"
    assert result["reply_text"] == "Shukriya! Yeh sahi hai?"


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
async def test_confirm_profile_saves_pre_generated_pin_when_present():
    """Login roadmap item 1: a PIN shown in a corner badge from before the
    conversation even started (e.g. she tapped "I'm new" on the landing
    screen) must be the exact PIN that ends up saved -- not a different one
    minted here, which would silently invalidate what she's been shown."""
    profile = {"name": "Sunita", "village": "Rampur", "interest": "tailoring"}
    session = db.create_session(learner_id=None, language="hi-IN")
    state = make_state(
        session_id=session.id,
        stage="confirm_profile",
        stage_step=1,
        profile=profile,
        transcript="haan sahi hai",
        consent_declined=False,
        pending_pin="8137",
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

    assert result["ui"]["profile"]["pin"] == "8137"
    found = db.get_learner_by_name_pin("Sunita", "8137")
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
    assert {o["id"] for o in result["ui"]["options"]} == {
        "hi-IN",
        "gu-IN",
        "pa-IN",
        "bn-IN",
        "en-IN",
    }


@pytest.mark.parametrize(
    ("spoken", "expected"),
    [
        ("mujhe hindi aati hai", "hi-IN"),
        ("હું ગુજરાતી બોલું છું", "gu-IN"),
        ("English please", "en-IN"),
        ("इंग्लिश", "en-IN"),  # unhinted STT transliterates into Devanagari
        ("ਪੰਜਾਬੀ ਬੋਲਦੀ ਹਾਂ", "pa-IN"),
        ("আমি বাংলা বলতে পারি", "bn-IN"),
        ("bengali please", "bn-IN"),
        ("gu-IN", "gu-IN"),  # a tapped card arrives as the bare id
        ("bn-IN", "bn-IN"),
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
