from typing import Literal, TypedDict

Stage = Literal[
    "greet",
    "discover",
    "assess",
    "confirm_profile",
    "teach",
    "viva",
    "reteach",
    "wrapup",
    "close",
    "resume",
]


class ProfileDraft(TypedDict, total=False):
    name: str
    village: str
    interest: str
    starting_level: Literal["new", "some", "experienced"]
    notes: str


class VivaState(TypedDict):
    question_ids_asked: list[str]
    grades: dict[str, str]


class HistoryTurn(TypedDict):
    role: Literal["user", "mentor"]
    text: str


class AgentState(TypedDict):
    session_id: str
    learner_id: str | None
    language: str
    stage: Stage
    transcript: str
    history: list[HistoryTurn]
    profile: ProfileDraft | None
    lesson_id: str | None
    step_index: int
    viva: VivaState
    reteach_counts: dict[str, int]
    reply_text: str
    ui: dict  # serialized UICommand; validated against app.models.ui.UICommand at the API boundary


def initial_state(
    *,
    session_id: str,
    learner_id: str | None,
    language: str,
    stage: Stage = "greet",
    profile: ProfileDraft | None = None,
) -> AgentState:
    return AgentState(
        session_id=session_id,
        learner_id=learner_id,
        language=language,
        stage=stage,
        transcript="",
        history=[],
        profile=profile,
        lesson_id=None,
        step_index=0,
        viva=VivaState(question_ids_asked=[], grades={}),
        reteach_counts={},
        reply_text="",
        ui={"type": "idle"},
    )
