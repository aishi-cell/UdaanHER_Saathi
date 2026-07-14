from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field


class IdleCommand(BaseModel):
    type: Literal["idle"] = "idle"


class OptionCard(BaseModel):
    id: str
    label: str
    # Optional: language cards (choose_language) are text-only.
    image: str | None = None


class ShowOptionsCommand(BaseModel):
    type: Literal["show_options"] = "show_options"
    prompt: str
    options: list[OptionCard]


class ShowLessonStepCommand(BaseModel):
    type: Literal["show_lesson_step"] = "show_lesson_step"
    lesson_id: str
    step_index: int
    total_steps: int
    # Optional (plan v2): voice is the interface; a step's visual is an aid,
    # not a requirement. None renders as a caption-only card.
    image: str | None = None
    caption: str


class ShowVideoCommand(BaseModel):
    type: Literal["show_video"] = "show_video"
    url: str
    caption: str


class LearnerProfile(BaseModel):
    name: str
    village: str
    language: str
    interest: str
    starting_level: Literal["new", "some", "experienced"]
    notes: str
    # Set only on the card shown right after her profile is saved (T22):
    # the 4-digit return PIN, displayed as well as spoken so a missed
    # sentence doesn't lock her out of resuming.
    pin: str | None = None


class ShowProfileCardCommand(BaseModel):
    type: Literal["show_profile_card"] = "show_profile_card"
    profile: LearnerProfile


class ProgressLesson(BaseModel):
    lesson_id: str
    title: str
    status: Literal["done", "current", "locked"]


class ProgressConcept(BaseModel):
    concept_id: str
    label: str
    mastery: Literal["strong", "shaky", "unseen"]


class ProgressPayload(BaseModel):
    skill: str
    lessons: list[ProgressLesson]
    concepts: list[ProgressConcept]
    next_step_text: str


class ShowProgressCommand(BaseModel):
    type: Literal["show_progress"] = "show_progress"
    payload: ProgressPayload


UICommand = Annotated[
    Union[
        IdleCommand,
        ShowOptionsCommand,
        ShowLessonStepCommand,
        ShowVideoCommand,
        ShowProfileCardCommand,
        ShowProgressCommand,
    ],
    Field(discriminator="type"),
]
