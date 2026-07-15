from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agent.nodes import (
    assess,
    choose_language,
    practice,
    close,
    confirm_profile,
    discover,
    earn,
    greet,
    reteach,
    resume,
    teach,
    viva,
    wrapup,
)
from app.agent.state import AgentState, Stage

STAGE_NODES: dict[Stage, object] = {
    "choose_language": choose_language,
    "greet": greet,
    "discover": discover,
    "assess": assess,
    "confirm_profile": confirm_profile,
    "teach": teach,
    "viva": viva,
    "reteach": reteach,
    "practice": practice,
    "earn": earn,
    "wrapup": wrapup,
    "close": close,
    "resume": resume,
}


def route_by_stage(state: AgentState) -> Stage:
    """Conditional entry point: dispatches to the node matching the
    checkpointed `stage`. Node-level guards (app.agent.guards) enforce the
    Spec S9.1 hard rules, e.g. teach.py refuses to teach without a profile."""
    return state["stage"]


def build_graph() -> StateGraph:
    builder = StateGraph(AgentState)

    for name, module in STAGE_NODES.items():
        builder.add_node(name, module.run)
        builder.add_edge(name, END)

    builder.add_conditional_edges(
        START,
        route_by_stage,
        {name: name for name in STAGE_NODES},
    )

    return builder


def compile_graph(checkpointer) -> CompiledStateGraph:
    return build_graph().compile(checkpointer=checkpointer)
