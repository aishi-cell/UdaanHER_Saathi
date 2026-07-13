"""On-the-fly visual aid: LLM-drawn SVG line diagrams (plan v2).

When re-teaching a concept that has no vetted video in the store, the mentor
may generate a simple labeled diagram live. SVG, never diffusion images:
line diagrams are fast, cheap, consistent, and low-literacy-friendly (see
plan v2 feasibility findings). Visuals are always optional aids -- the spoken
explanation must stand alone without them.
"""

from __future__ import annotations

import base64
import logging
import re

from pydantic import BaseModel, Field

from app.services.llm import get_chat_model

logger = logging.getLogger(__name__)

SVG_SYSTEM = """You draw minimal instructional line diagrams as SVG for low-literacy viewers.

Rules:
- One idea per diagram. At most 6 shapes. Thick strokes (stroke-width 4+), high contrast.
- viewBox="0 0 400 300". No external references, no <script>, no <image>, no CSS imports.
- At most 3 short text labels, font-size 24+, simple everyday words in {language_name}.
- Prefer showing the RIGHT way vs the WRONG way side by side when warning about a mistake
  (mark the wrong side with a large X).
Return only the SVG markup."""


class SvgOut(BaseModel):
    svg: str = Field(description="Complete <svg>...</svg> markup, nothing else")


# Reject active/external content, but allow same-document fragment references
# (url(#marker), href="#id") -- models legitimately use those for arrowheads
# and gradients, and they can't exfiltrate or execute anything.
_FORBIDDEN = re.compile(
    r"<\s*(script|image|foreignObject)"
    r"|href\s*=\s*(?![\"']?#)"
    r"|url\s*\(\s*(?![\"']?#)",
    re.IGNORECASE,
)
_SVG_TAG = re.compile(r"<svg[\s>].*</svg>", re.DOTALL | re.IGNORECASE)

_LANGUAGE_NAMES = {"hi": "Hindi", "gu": "Gujarati", "en": "English"}


def _sanitize(svg: str) -> str | None:
    match = _SVG_TAG.search(svg)
    if not match:
        return None
    svg = match.group(0)
    if _FORBIDDEN.search(svg):
        return None
    return svg


def to_data_uri(svg: str) -> str:
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


async def generate_diagram(concept_label: str, teaching_notes: str, *, language: str) -> str | None:
    """Returns a data: URI for a simple diagram of the concept, or None if
    generation failed/was unsafe -- callers must degrade to voice-only."""
    language_name = _LANGUAGE_NAMES.get(language.split("-")[0], "English")
    try:
        llm = get_chat_model(temperature=0.4).with_structured_output(SvgOut)
        result: SvgOut = await llm.ainvoke(
            [
                {"role": "system", "content": SVG_SYSTEM.format(language_name=language_name)},
                {
                    "role": "user",
                    "content": (
                        f"Concept: {concept_label}\n"
                        f"What the diagram must convey: {teaching_notes}"
                    ),
                },
            ]
        )
    except Exception:
        logger.exception("visuals: diagram generation failed for %r", concept_label)
        return None

    svg = _sanitize(result.svg)
    if svg is None:
        logger.warning("visuals: generated SVG rejected by sanitizer for %r", concept_label)
        return None
    return to_data_uri(svg)
