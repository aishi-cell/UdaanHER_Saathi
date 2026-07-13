from typing import Literal, TypedDict

Stage = Literal[
    "greet",
    "discover",
    "assess",
    "confirm_profile",
    "teach",
    "viva",
    "reteach",
    "earn",
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
    # Plan v2 (docs/app_plan_v2.md): the skill she chose (a content-store id),
    # assess's per-concept diagnosis ("knows" | "gap"), and the personalized
    # path -- the ordered gap-concept ids teach walks through. step_index
    # indexes into the store steps filtered to learning_path.
    skill_id: str | None
    concept_estimates: dict[str, str]
    learning_path: list[str]
    reply_text: str
    ui: dict  # serialized UICommand; validated against app.models.ui.UICommand at the API boundary
    # Not in Spec S9.2's illustrative shape, but needed to run a real
    # multi-exchange conversation within a single node while the graph stays
    # one-node-per-turn: how many sub-turns have happened since a node last
    # advanced `stage`. Reset to 0 by whichever node writes a new stage.
    stage_step: int
    # Set by greet on a spoken "no" to remembering her (Spec S12); honoured
    # by confirm_profile, which skips the DB save but lets the session
    # continue normally.
    consent_declined: bool


def initial_state(
    *,
    session_id: str,
    learner_id: str | None,
    language: str,
    stage: Stage = "greet",
    profile: ProfileDraft | None = None,
    skill_id: str | None = None,
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
        skill_id=skill_id,
        concept_estimates={},
        learning_path=[],
        reply_text="",
        ui={"type": "idle"},
        stage_step=0,
        consent_declined=False,
    )
