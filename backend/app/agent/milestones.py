"""Career roadmap ("My Journey", roadmap item 3): the bigger arc across a
skill -- started it, made something with it, learned to price it, finished
it, found a customer, made a sale -- as opposed to the concept-level mastery
`teach`/`viva` already track.

The roadmap lists these milestones in an illustrative order ("completed a
skill" before "made the first usable product"); CATALOG instead orders them
the way they actually happen in one session (teach -> practice -> earn ->
wrapup), so a learner's list of them reads as a real sequence and
"next_step_text" means something.

The first four are auto-marked by the graph nodes at the moment they become
true (see each node's `db.mark_milestone` call). The last two happen in her
real life, off-platform -- there's no way to observe a real sale from inside
a conversation -- so they stay unmarked until a future voice-reported
mechanism exists (see docs/decisions.md / TODO.md item 3)."""

from typing import NamedTuple


class Milestone(NamedTuple):
    id: str
    label_hi: str
    label_en: str
    auto_tracked: bool


CATALOG: list[Milestone] = [
    Milestone("started_skill", "सीखना शुरू किया", "Started learning", True),
    Milestone("made_product", "पहली चीज़ बनाई", "Made the first thing", True),
    Milestone("learned_pricing", "कीमत तय करना सीखा", "Learned to set a price", True),
    Milestone("completed_skill", "हुनर पूरा सीख लिया", "Completed the skill", True),
    Milestone("found_customer", "पहला ग्राहक मिला", "Found the first customer", False),
    Milestone("first_paid_order", "पहला ऑर्डर पूरा किया", "Completed the first paid order", False),
]

MILESTONE_IDS = {m.id for m in CATALOG}
