import pytest
from pydantic import BaseModel, TypeAdapter, ValidationError

from app.models.ui import UICommand

adapter: TypeAdapter = TypeAdapter(UICommand)


class _Wrapper(BaseModel):
    ui: UICommand


EXAMPLES = [
    {"type": "idle"},
    {
        "type": "show_options",
        "prompt": "What would you like to learn?",
        "options": [
            {"id": "tailoring", "label": "Tailoring", "image": "assets/tailoring.png"},
            {"id": "beauty", "label": "Beauty", "image": "assets/beauty.png"},
        ],
    },
    {
        "type": "show_lesson_step",
        "lesson_id": "tail-01-measure",
        "step_index": 1,
        "total_steps": 4,
        "image": "assets/tail01_step1.png",
        "caption": "Measure shoulder to waist.",
    },
    {
        "type": "show_video",
        "url": "https://youtube.com/embed/abc123",
        "caption": "How to thread a needle",
    },
    {
        "type": "show_profile_card",
        "profile": {
            "name": "Sunita",
            "village": "Rampur",
            "language": "gu-IN",
            "interest": "tailoring",
            "starting_level": "some",
            "notes": "Comfortable with basic stitches.",
        },
    },
    {
        "type": "show_progress",
        "payload": {
            "skill": "tailoring",
            "lessons": [{"lesson_id": "tail-01-measure", "title": "Measuring", "status": "done"}],
            "concepts": [
                {"concept_id": "c-body-measure", "label": "Body measurement", "mastery": "strong"}
            ],
            "next_step_text": "Next: cutting.",
        },
    },
]


@pytest.mark.parametrize("example", EXAMPLES, ids=[e["type"] for e in EXAMPLES])
def test_each_command_type_round_trips(example):
    parsed = adapter.validate_python(example)
    assert parsed.type == example["type"]
    dumped = adapter.dump_python(parsed, mode="json")
    assert dumped == example


def test_unknown_type_is_rejected():
    with pytest.raises(ValidationError):
        adapter.validate_python({"type": "not_a_real_command"})


def test_starting_level_is_constrained():
    with pytest.raises(ValidationError):
        _Wrapper.model_validate(
            {
                "ui": {
                    "type": "show_profile_card",
                    "profile": {
                        "name": "Sunita",
                        "village": "Rampur",
                        "language": "gu-IN",
                        "interest": "tailoring",
                        "starting_level": "expert",
                        "notes": "",
                    },
                }
            }
        )


def test_mastery_is_constrained():
    with pytest.raises(ValidationError):
        _Wrapper.model_validate(
            {
                "ui": {
                    "type": "show_progress",
                    "payload": {
                        "skill": "tailoring",
                        "lessons": [],
                        "concepts": [
                            {"concept_id": "c1", "label": "x", "mastery": "excellent"}
                        ],
                        "next_step_text": "",
                    },
                }
            }
        )
