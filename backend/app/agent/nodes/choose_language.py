"""choose_language node: Saathi speaks FIRST and takes the language by voice.

The session opens here when no language was given (the voice-first path).
The prompt is canned trilingual text -- deterministic, no LLM -- and her
answer is matched in code by keyword (or a tapped card arrives as the bare
BCP-47 id). On a match the node runs greet's opening in her language in the
same turn, so choosing a language never costs her an extra exchange.
"""

import re

from app.agent.nodes import greet
from app.agent.state import AgentState

PROMPT_TEXT = (
    "नमस्ते! आप कौन सी भाषा बोलेंगी? हिन्दी, ગુજરાતી, ਪੰਜਾਬੀ, বাংলা, या English? "
    "Please say your language."
)
REASK_TEXT = (
    "फिर से बताइए -- हिन्दी, ગુજરાતી, ਪੰਜਾਬੀ, বাংলা, या English? "
    "You can also tap your language on the screen."
)

# The prompt mixes scripts; Sarvam needs one target language for TTS.
PROMPT_TTS_LANGUAGE = "hi-IN"

# Language expansion (roadmap item 7), priority order as given: Bengali,
# Kannada, Malayalam, Marathi, Odia, Tamil, Telugu. Bengali is the first
# one landed -- Sarvam STT/TTS support confirmed via a live round-trip
# check (2026-09-26); content translations are AI drafts pending native-
# speaker review before this is considered launched (see TODO.md item 7).
LANGUAGE_OPTIONS = [
    {"id": "hi-IN", "label": "हिन्दी", "image": None},
    {"id": "gu-IN", "label": "ગુજરાતી", "image": None},
    {"id": "pa-IN", "label": "ਪੰਜਾਬੀ", "image": None},
    {"id": "bn-IN", "label": "বাংলা", "image": None},
    {"id": "en-IN", "label": "English", "image": None},
]

_KNOWN_LANGUAGE_IDS = {opt["id"] for opt in LANGUAGE_OPTIONS}

# Her language name often arrives transliterated INTO another script by the
# unhinted STT (live test: spoken "English" came back as "इंग्लिश" and never
# matched) -- cover each language's name in every script we can meet.
_PATTERNS: list[tuple[str, str]] = [
    (r"hindi|हिन्दी|हिंदी|હિન્દી|ਹਿੰਦੀ|hindee", "hi-IN"),
    (r"gujarati|guj[ae]rati|ગુજરાતી|गुजराती|ਗੁਜਰਾਤੀ|gujju", "gu-IN"),
    (r"punjabi|panjabi|ਪੰਜਾਬੀ|पंजाबी|પંજાબી", "pa-IN"),
    (r"bengali|bangla|বাংলা|बंगाली|બંગાળી|ਬੰਗਾਲੀ", "bn-IN"),
    (
        r"english|angrezi|angreji|inglish|inglis|अंग्रेज़ी|अंग्रेजी|इंग्लिश|इंगलिश|"
        r"અંગ્રેજી|ઇંગ્લિશ|ਅੰਗਰੇਜ਼ੀ|ਇੰਗਲਿਸ਼",
        "en-IN",
    ),
]


def match_language(transcript: str) -> str | None:
    text = (transcript or "").strip()
    if text in _KNOWN_LANGUAGE_IDS:  # a tapped card
        return text
    lowered = text.lower()
    for pattern, code in _PATTERNS:
        if re.search(pattern, lowered):
            return code
    return None


def _options_ui(prompt: str) -> dict:
    return {"type": "show_options", "prompt": prompt, "options": LANGUAGE_OPTIONS}


async def run(state: AgentState) -> dict:
    if state["stage_step"] == 0:
        return {
            "stage": "choose_language",
            "stage_step": 1,
            "reply_text": PROMPT_TEXT,
            "ui": _options_ui(PROMPT_TEXT),
        }

    language = match_language(state["transcript"])
    if language is None:
        return {
            "stage": "choose_language",
            "stage_step": 1,
            "reply_text": REASK_TEXT,
            "ui": _options_ui(REASK_TEXT),
        }

    # Same turn: her language is set AND greet asks its first question, so
    # the reply she hears is already in her language.
    result = await greet.run(
        {**state, "language": language, "stage": "greet", "stage_step": 0, "transcript": ""}
    )
    return {**result, "language": language}
