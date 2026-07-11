from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field


class IdleCommand(BaseModel):
    type: Literal["idle"] = "idle"


class OptionCard(BaseModel):
    id: str
    label: str
    image: str


class ShowOptionsCommand(BaseModel):
    type: Literal["show_options"] = "show_options"
    prompt: str
    options: list[OptionCard]


class ShowLessonStepCommand(BaseModel):
    type: Literal["show_lesson_step"] = "show_lesson_step"
    lesson_id: str
    step_index: int
    total_steps: int
    image: str
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
