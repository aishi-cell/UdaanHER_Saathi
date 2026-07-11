import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from app.agent.graph import compile_graph
from app.agent.guards import can_start_reteach
from app.agent.state import initial_state

EXPECTED_STAGE_SEQUENCE = [
    "discover",
    "assess",
    "confirm_profile",
    "teach",
    "viva",
    "wrapup",
    "close",
]


@pytest.mark.asyncio
async def test_stage_sequence_walks_the_full_pedagogy_in_order():
    graph = compile_graph(InMemorySaver())
    config = {"configurable": {"thread_id": "seq-test"}}

    state = initial_state(session_id="seq-test", learner_id=None, language="hi-IN")
    result = await graph.ainvoke(state, config=config)
    assert result["stage"] == EXPECTED_STAGE_SEQUENCE[0]

    for expected_stage in EXPECTED_STAGE_SEQUENCE[1:]:
        result = await graph.ainvoke({"transcript": "ok"}, config=config)
        assert result["stage"] == expected_stage


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
    )
    result = await graph.ainvoke(state, config=config)

    assert result["stage"] == "viva"


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

    async with AsyncSqliteSaver.from_conn_string(str(db_path)) as saver:
        graph = compile_graph(saver)
        state = initial_state(session_id="restart-test", learner_id=None, language="hi-IN")
        result = await graph.ainvoke(state, config=config)
        result = await graph.ainvoke({"transcript": "ok"}, config=config)
        assert result["stage"] == "assess"

    # New connection, new compiled graph -- same underlying file.
    async with AsyncSqliteSaver.from_conn_string(str(db_path)) as saver:
        graph = compile_graph(saver)
        result = await graph.ainvoke({"transcript": "ok"}, config=config)
        assert result["stage"] == "confirm_profile"
