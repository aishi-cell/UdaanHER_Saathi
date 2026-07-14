from contextlib import ExitStack
from unittest.mock import AsyncMock, patch

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from app.agent.graph import compile_graph
from app.agent.guards import can_start_reteach
from app.agent.nodes.assess import DiagnosticExtraction
from app.agent.nodes.confirm_profile import ConfirmationExtraction
from app.agent.nodes.discover import VillageWorkExtraction
from app.agent.nodes.greet import ConsentExtraction, GreetExtraction
from app.agent.state import initial_state
from app.models import db


@pytest.fixture(autouse=True)
def temp_db(tmp_path):
    db.configure_engine(f"sqlite:///{tmp_path / 'test.db'}")
    db.init_db()
    yield
    db._engine = None


def _greet_extractor(consent_given: bool = True):
    """greet runs two different extractions (name+returning at step 1,
    consent at step 2) through the same patched function -- answer by
    the schema it was asked for."""

    async def extract(*_args, **kwargs):
        if kwargs["schema"] is GreetExtraction:
            return GreetExtraction(name="Sunita", returning=False)
        return ConsentExtraction(consent_given=consent_given)

    return extract


def _mock_onboarding_llm(stack: ExitStack) -> None:
    """Patches every real node's LLM calls so a full graph walk from greet
    through confirm_profile runs deterministically, without hitting OpenAI."""
    for module in ("greet", "discover", "assess", "confirm_profile"):
        stack.enter_context(
            patch(
                f"app.agent.nodes.{module}.ask_conversational",
                new=AsyncMock(return_value="ok"),
            )
        )

    stack.enter_context(
        patch(
            "app.agent.nodes.greet.extract_structured",
            new=AsyncMock(side_effect=_greet_extractor(consent_given=True)),
        )
    )
    stack.enter_context(
        patch(
            "app.agent.nodes.discover.extract_structured",
            new=AsyncMock(
                return_value=VillageWorkExtraction(village="Rampur", work_notes="farming")
            ),
        )
    )
    stack.enter_context(
        patch(
            "app.agent.nodes.assess.extract_structured",
            new=AsyncMock(
                return_value=DiagnosticExtraction(
                    starting_level="some", notes="ok", concept_estimates=[]
                )
            ),
        )
    )
    stack.enter_context(
        patch(
            "app.agent.nodes.confirm_profile.extract_structured",
            new=AsyncMock(return_value=ConfirmationExtraction(confirmed=True)),
        )
    )


# Exact turn-by-turn shape of a full onboarding walk. Each stage's step-0
# turn only *asks* (it ignores whatever transcript arrives with it), so the
# turn count per stage is one more than the number of real answers it needs:
# greet needs 3 invocations (ask name + new/returning, extract + ask consent
# for a new visitor, extract consent), discover needs 3 (ask village/work,
# extract + show interest cards, receive interest), assess needs 4 (3
# questions asked + 1 final extraction), and confirm_profile needs 2
# (readback, then extract confirmation).
ONBOARDING_TURNS_AFTER_INITIAL_GREET = [
    "Sunita, pehli baar",  # greet step1: extract name + new visitor -> ask consent
    "haan, yaad rakho",  # greet step2: extract consent -> discover
    "namaste",  # discover step0: ask village/work (content ignored)
    "Rampur mein kheti karti hoon",  # discover step1: extract, show interest cards
    "tailoring",  # discover step2: tap interest -> assess
    "haan",  # assess step0 -> step1 (Q1 asked)
    "haan",  # assess step1 -> step2 (Q2 asked)
    "haan",  # assess step2 -> step3 (Q3 asked)
    "haan, thoda seekha hai",  # assess step3: extract level -> confirm_profile
    "haan",  # confirm_profile step0: readback (content ignored)
    "haan sahi hai",  # confirm_profile step1: extract confirmation -> save -> teach
]


async def _run_full_onboarding(graph, config, session_id: str):
    # session_id must be a genuine sessions row -- confirm_profile's real
    # save path calls link_session_to_learner, exactly like production,
    # where session_id always comes from db_repo.create_session().
    state = initial_state(session_id=session_id, learner_id=None, language="hi-IN")
    result = await graph.ainvoke(state, config=config)
    assert result["stage"] == "greet"

    results = []
    for transcript in ONBOARDING_TURNS_AFTER_INITIAL_GREET:
        result = await graph.ainvoke({"transcript": transcript}, config=config)
        results.append(result)
    return results


@pytest.mark.asyncio
async def test_stage_sequence_walks_the_full_onboarding_in_order():
    graph = compile_graph(InMemorySaver())
    session = db.create_session(learner_id=None, language="hi-IN")
    config = {"configurable": {"thread_id": session.id}}

    with ExitStack() as stack:
        _mock_onboarding_llm(stack)
        results = await _run_full_onboarding(graph, config, session.id)

    stages = [r["stage"] for r in results]
    assert stages == [
        "greet",  # new visitor: consent question asked
        "discover",  # consent extracted
        "discover",  # asked village/work
        "discover",  # extracted village, showing interest cards
        "assess",  # tapped interest
        "assess",  # Q1 asked
        "assess",  # Q2 asked
        "assess",  # Q3 asked
        "confirm_profile",  # level extracted
        "confirm_profile",  # readback shown
        "teach",  # confirmed and saved
    ]
    assert results[3]["ui"]["type"] == "show_options"
    assert results[-1]["learner_id"] is not None


@pytest.mark.asyncio
async def test_declining_consent_reaches_teach_with_empty_database():
    graph = compile_graph(InMemorySaver())
    session = db.create_session(learner_id=None, language="hi-IN")
    config = {"configurable": {"thread_id": session.id}}

    with ExitStack() as stack:
        _mock_onboarding_llm(stack)
        stack.enter_context(
            patch(
                "app.agent.nodes.greet.extract_structured",
                new=AsyncMock(side_effect=_greet_extractor(consent_given=False)),
            )
        )
        results = await _run_full_onboarding(graph, config, session.id)

    assert results[1]["consent_declined"] is True
    assert results[-1]["stage"] == "teach"
    assert results[-1]["learner_id"] is None
    with db.get_db_session() as s:
        from sqlmodel import select

        assert s.exec(select(db.Learner)).all() == []


@pytest.mark.asyncio
async def test_close_is_terminal():
    graph = compile_graph(InMemorySaver())
    config = {"configurable": {"thread_id": "terminal-test"}}

    state = initial_state(
        session_id="terminal-test", learner_id=None, language="hi-IN", stage="close"
    )
    result = await graph.ainvoke(state, config=config)
    assert result["stage"] == "close"

    result = await graph.ainvoke({"transcript": "anything"}, config=config)
    assert result["stage"] == "close"


@pytest.mark.asyncio
async def test_guard_teach_is_unreachable_without_a_profile():
    graph = compile_graph(InMemorySaver())
    config = {"configurable": {"thread_id": "guard-teach-test"}}

    state = initial_state(
        session_id="guard-teach-test",
        learner_id=None,
        language="hi-IN",
        stage="teach",
        profile=None,
    )
    result = await graph.ainvoke(state, config=config)

    assert result["stage"] != "teach"
    assert result["stage"] == "confirm_profile"


@pytest.mark.asyncio
async def test_guard_teach_proceeds_once_a_profile_exists():
    graph = compile_graph(InMemorySaver())
    config = {"configurable": {"thread_id": "guard-teach-ok-test"}}

    state = initial_state(
        session_id="guard-teach-ok-test",
        learner_id=None,
        language="hi-IN",
        stage="teach",
        profile={"name": "Sunita", "interest": "tailoring", "starting_level": "some"},
        skill_id="tailoring",  # seeded content-store skill
    )
    with patch(
        "app.agent.nodes.teach.ask_conversational", new=AsyncMock(return_value="ok")
    ):
        result = await graph.ainvoke(state, config=config)

    # Not redirected to confirm_profile: teaching actually began (step 0 of
    # her path, with the lesson-step command on screen).
    assert result["stage"] == "teach"
    assert result["ui"]["type"] == "show_lesson_step"


def test_guard_reteach_caps_at_two_rounds():
    assert can_start_reteach("c-body-measure", {}) is True
    assert can_start_reteach("c-body-measure", {"c-body-measure": 1}) is True
    assert can_start_reteach("c-body-measure", {"c-body-measure": 2}) is False
    assert can_start_reteach("c-body-measure", {"c-body-measure": 3}) is False
    # Unrelated concepts' counts don't leak into this one.
    assert can_start_reteach("c-fabric-grain", {"c-body-measure": 2}) is True


@pytest.mark.asyncio
async def test_checkpoint_survives_reopening_the_sqlite_connection(tmp_path):
    """Simulates a backend restart: the graph is compiled against a fresh
    AsyncSqliteSaver connection pointed at the same file, twice."""
    db_path = tmp_path / "checkpoints.db"
    config = {"configurable": {"thread_id": "restart-test"}}

    with ExitStack() as stack:
        _mock_onboarding_llm(stack)

        async with AsyncSqliteSaver.from_conn_string(str(db_path)) as saver:
            graph = compile_graph(saver)
            state = initial_state(session_id="restart-test", learner_id=None, language="hi-IN")
            result = await graph.ainvoke(state, config=config)
            result = await graph.ainvoke({"transcript": "Sunita, pehli baar"}, config=config)
            assert result["stage"] == "greet"  # new visitor: consent question

        # New connection, new compiled graph -- same underlying file. The
        # restart lands mid-greet, so the consent answer must still resolve.
        async with AsyncSqliteSaver.from_conn_string(str(db_path)) as saver:
            graph = compile_graph(saver)
            result = await graph.ainvoke({"transcript": "haan, yaad rakho"}, config=config)
            assert result["stage"] == "discover"  # consent extracted

            result = await graph.ainvoke({"transcript": "namaste"}, config=config)
            assert result["stage"] == "discover"  # asked village/work

            result = await graph.ainvoke({"transcript": "Rampur mein kheti"}, config=config)
            assert result["stage"] == "discover"
            assert result["ui"]["type"] == "show_options"
