# Tailoring Curriculum Plan (T15–T17)

**Status:** finalized blueprint, ready to transcribe into JSON.
**Source of truth:** NSDC Qualification Pack — *Sewing Machine Operator (AMH/Q0301)* and
*Assistant Tailor (AMH/Q1947)*, National Qualification Register (https://nqr.gov.in).
**Quality bar:** a working tailor reading a lesson's teaching notes would nod.
**Review gate:** lesson 1 notes reviewed by a real tailor before T15 is signed off (task book T15).

This plan covers all three content tasks because they share the same `concept_id`s:
- **T15** → `content/curriculum/tailoring.json` (lessons, concepts, steps)
- **T16** → `content/rubrics/tailoring_rubrics.json` (viva questions per concept)
- **T17** → `content/visual_aids/index.json` (≥2 vetted aids per concept)

---

## Scope decision

Three lessons for the MVP, in the natural order a beginner learns the trade —
**measure → cut → stitch** — because you cannot cut without measuring and cannot
sew a garment without cutting. This is also the task book's suggested triple.

| # | lesson_id | Title | Why first |
|---|-----------|-------|-----------|
| 1 | `tail-01-measure` | Taking body measurements | The foundation; every garment starts here. No machine needed — safe first win. |
| 2 | `tail-02-cutting`  | Fabric grain & cutting basics | Bridges measurement to construction; grain is the concept beginners most often get wrong. |
| 3 | `tail-03-seams`    | Straight-stitch seams & finishing | First real machine work; the single most-used skill in all garment construction. |

Only **tailoring** is authored for the MVP. The other discover-stage cards
(beauty, handicrafts, cooking) remain UI-only placeholders (see `docs/decisions.md`).

---

## Lesson 1 — `tail-01-measure` · Taking body measurements

**Concepts** (graded in viva):

| concept_id | label (en) | must_land | What "understanding" means |
|---|---|---|---|
| `c-tape-basics`    | Using the measuring tape | ✅ | Knows the soft inch-tape, that it bends round the body, reads the numbers. |
| `c-measure-points` | Where to measure          | ✅ | Knows the key points: bust, waist, hip, shoulder, length, sleeve. |
| `c-tape-tension`   | Snug, not tight; level    | ✅ | Tape firm but not pulled; kept parallel to the floor / level all the way round. |
| `c-record-order`   | Recording in order        | ⬜ | Writes/says each number in a consistent order so none is forgotten. |

**Steps** (one screen each — image + spoken narration from teaching_notes):

| step | image | teaching_notes (draft, English, for the LLM) |
|---|---|---|
| 0 | inch tape | Introduce the soft inch-tape — the tailor's most important tool. It bends around the body, unlike a hard ruler. It reads in inches. Keep it warm: "this little tape is where every dress begins." |
| 1 | tape around bust | Measuring the bust: wrap the tape around the **fullest** part of the chest, keep it level all the way round the back, snug but not tight. Warn clearly: pulling the tape tight is the most common beginner mistake — the blouse then comes out too small. |
| 2 | tape around waist | Measuring the waist: find the **narrowest** part, usually just above the navel. Keep the tape parallel to the floor, not slanting down. |
| 3 | tape around hip | Measuring the hip: around the **widest** part of the hips, standing with feet together so the number is honest. |
| 4 | shoulder + length | Two more: shoulder width (edge of one shoulder to the other across the back) and garment length (from shoulder or neck down to where the garment should end). |
| 5 | notebook with numbers | Emphasise writing each number down **immediately, in the same order every time** (bust, waist, hip, shoulder, length) so nothing is forgotten or swapped. |

**common_mistakes:** tape pulled too tight; tape twisted or slanting instead of level;
measuring over thick clothes; forgetting to write the number before taking the next.

---

## Lesson 2 — `tail-02-cutting` · Fabric grain & cutting basics

**Concepts:**

| concept_id | label (en) | must_land | What "understanding" means |
|---|---|---|---|
| `c-grain`          | Fabric grain (direction) | ✅ | Fabric has a direction; along the selvedge (straight grain) is strong, diagonal (bias) stretches. Cutting off-grain makes garments hang crooked. |
| `c-layout`         | Folding & placing pattern | ✅ | Fold fabric with right sides together; place the pattern aligned to the straight grain before cutting. |
| `c-seam-allowance` | Leaving seam allowance    | ✅ | Cut a margin (≈ ½"–¾") **beyond** the marked line so there is fabric to sew the seam. |
| `c-cut-technique`  | Cutting cleanly           | ⬜ | Fabric flat on the table, long smooth scissor strokes along the chalk line, non-cutting hand holding fabric steady. |

**Steps:**

| step | image | teaching_notes (draft) |
|---|---|---|
| 0 | selvedge / weave close-up | Fabric is not the same in every direction. The tight finished edge is the **selvedge**; the direction along it is the straight grain — the strongest, most stable direction. |
| 1 | grain arrows (straight vs bias) | Straight grain (along selvedge) holds its shape; the **bias** (diagonal) stretches. Cutting a garment off-grain makes it twist and hang crooked on the body. |
| 2 | fabric folded, right sides in | Fold the fabric neatly, usually right sides together, edges matching, so both halves cut identically. |
| 3 | paper pattern aligned to grain | Place the pattern piece so its grain-line arrow runs **parallel to the selvedge**. Pin it flat before touching the scissors. |
| 4 | chalk line + seam allowance margin | Mark round the pattern with chalk, then mark a second line ≈ ½"–¾" **outside** it — that extra strip is the seam allowance you'll sew into. Warn: cutting on the exact body line leaves no fabric to join the seam. |
| 5 | scissors cutting flat on table | Keep the fabric flat on the table (don't lift it up), cut with long smooth strokes along the outer line, the other hand holding the fabric steady just ahead of the blades. |

**common_mistakes:** ignoring grain / cutting diagonally; forgetting seam allowance and
cutting on the body line; lifting the fabric off the table while cutting (wobbly edge);
folding with edges not matching so the two halves differ.

---

## Lesson 3 — `tail-03-seams` · Straight-stitch seams & finishing

**Concepts:**

| concept_id | label (en) | must_land | What "understanding" means |
|---|---|---|---|
| `c-machine-safe`  | Machine basics & safety | ✅ | Knows the needle, presser foot, and foot pedal; keeps fingers clear of the needle; starts slow. |
| `c-straight-seam` | Sewing a straight seam  | ✅ | Sews a straight line at a steady seam allowance, using the plate guide, hands **guiding** not pulling the fabric. |
| `c-backstitch`    | Locking the stitches    | ✅ | Backstitches (reverse) a few stitches at the start and end so the seam doesn't unravel. |
| `c-seam-finish`   | Pressing & finishing    | ⬜ | Presses the seam open/to one side; finishes the raw edge so it doesn't fray. |

**Steps:**

| step | image | teaching_notes (draft) |
|---|---|---|
| 0 | machine parts labelled | Point out the three things she must know first: the **needle** (goes up and down, keep fingers away), the **presser foot** (holds fabric down), the **pedal** (controls speed — press gently). Safety first, warmly: "the machine is fast, so we go slow until our hands trust it." |
| 1 | threaded machine / bobbin | Briefly: the top thread and the bobbin thread below must both be ready; the fabric goes under the raised presser foot, then the foot comes down to hold it. (Keep light — full threading is its own future lesson.) |
| 2 | fabric at the seam guide | Line the fabric edge up with the seam-allowance guide line on the metal plate — that keeps the stitching a steady distance from the edge without measuring each time. |
| 3 | sewing a straight line | Press the pedal gently, let the machine feed the fabric — hands only **guide** it, never pull (pulling bends the needle and skews the line). Keep the edge on the guide the whole way. |
| 4 | backstitch at start/end | At the start and again at the end, stitch forward a little, press reverse for 3–4 stitches, then forward again — this **locks** the seam so it won't come undone. |
| 5 | pressed & finished seam | Open the two fabric pieces, press the seam flat with an iron, and finish the raw edges (zig-zag or overlock) so the fabric doesn't fray with washing. |

**common_mistakes:** pulling the fabric through instead of letting it feed (crooked line,
broken needle); forgetting to backstitch (seam unravels); fingers too near the needle;
skipping pressing so the seam looks lumpy.

---

## T16 — Rubric plan (built on the concepts above)

For **every** `must_land` concept (and ideally the optional ones too), write
**2–3 conversational viva questions**, and for each question:
- **2–3 `sounds_right`** — how a correct answer sounds *spoken* by a non-literate learner:
  informal, code-mixed, incomplete-but-correct.
- **1–2 `sounds_confused`** — common misconception phrasings.

These are the LLM's grading context (grades are only `strong` / `shaky`).

Illustrative (concept `c-tape-tension`):
- **Q:** "Suppose the blouse comes out tight at the chest — what might have happened when we measured?"
- `sounds_right`: *"tape zyada tight kheech diya hoga"* · *"naap ke time tape dheela rakhna tha, thoda"* · *"kapde ke upar se naap liya hoga isliye"*
- `sounds_confused`: *"tape chhoti thi"* · *"machine kharab hai"*

Do this per concept across all three lessons. Have the other person answer each
question aloud and revise exemplars that don't match natural speech (task book T16).

## T17 — Visual-aid plan (built on the concepts above)

For each concept, curate **≥2** aids into `index.json`:
- Prefer a good **Hindi** (Gujarati rarer) YouTube tutorial **segment**, converted to
  `youtube.com/embed/<id>` form, **watched end to end** and verified it plays in an iframe.
- And/or a **clear diagram** in `content/assets/`.
- Each entry gets a one-line `note` on why it was chosen. **No live search — ever.**

Priority order for sourcing videos: the `must_land` concepts most likely to need a
re-teach — grain (`c-grain`), tape tension (`c-tape-tension`), backstitch (`c-backstitch`).

---

## Assets still to produce

~17 step images total (line diagrams beat photos; note licences), into `content/assets/`:
`tail01_step0..5`, `tail02_step0..5`, `tail03_step0..5`. Today the folder holds only
the earcon chime.

## Open decisions before transcribing to JSON

1. **Confirm the 3 lessons** above (measure / cut / stitch) — or swap any.
2. **Image approach:** simple hand-drawn/line SVG diagrams generated in-repo vs. sourced
   CC-licensed images. (SVG line diagrams are fastest and license-clean.)
3. **Tailor reviewer** for lesson 1 — who, and by when.
