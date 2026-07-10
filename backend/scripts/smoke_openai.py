"""Proves the OpenAI key works via one structured-output call (Spec S6.3).

Run from backend/: uv run python scripts/smoke_openai.py
"""

import sys
from pathlib import Path

from openai import OpenAI
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings


class OkResponse(BaseModel):
    ok: bool


def main() -> None:
    settings = get_settings()
    client = OpenAI(api_key=settings.openai_api_key)

    completion = client.beta.chat.completions.parse(
        model=settings.openai_model,
        messages=[
            {"role": "user", "content": "Return ok=true."},
        ],
        response_format=OkResponse,
    )
    parsed = completion.choices[0].message.parsed
    print("Parsed object:", parsed)
    print("Model used:", completion.model)


if __name__ == "__main__":
    main()
