# System Design — Question Intelligence System

Product and system design reference. Read before planning any feature. This document
defines *what* the system is and *how it behaves*, not what it is built with — see
`docs/TECH_ARCHITECTURE.md` and `docs/TECH_DECISIONS.md` for implementation.

---

## 1. Core Entities

### 1.1 Question

A Question is the central entity. It is modeled as one shape with a **type discriminator**
plus a **type-specific payload**, not as a separate table/model per question type. Every
question type shares the same lifecycle, review model, evaluation attachment, and
versioning — only the payload (what makes an MCQ an MCQ vs. a Fill-in-the-Blank) differs.

**Shared fields (every question, regardless of type):**
- `id` — stable identity for the question *lineage* (shared across all versions)
- `version` — integer, starts at 1, increments on edit
- `type` — discriminator: `mcq`, `true_false`, `fill_blank` (future: `essay`, `matching`,
  `ordering`)
- `status` — lifecycle stage (see 1.6)
- `stem` — the question text itself
- `difficulty` — target difficulty level, set at generation time (can be reviewer-adjusted)
- `topic` / `tags` — subject classification, used for retrieval, filtering, and dedup
  scoping
- `source` — `topic` (free-generated) or `document` (RAG-grounded), plus a link to the
  source Document if applicable
- `generation_metadata` — link to the metadata record for the generation call that
  produced this version (see Section 6)
- `parent_id` — null for an original; points to the prior version's `id`+`version` for an
  edit (see 1.7)
- `created_at`, `created_by` — `by` is either "system" (LLM) or an SME identifier

**Type-specific payload:**
- **MCQ**: `options` (list, each with text + correct flag), `correct_option_id`,
  `explanation` (why the correct answer is correct — also used as judge context)
- **True/False**: `correct_answer` (boolean), `explanation`
- **Fill in the Blank**: `answer` (accepted string or list of acceptable variants),
  `blank_position` marker within the stem, `case_sensitive` flag

Keeping payload type-specific but everything else shared is the single decision that makes
Section 8 (future types) cheap: a new type adds a new payload shape and a new
generator/evaluator pair, and touches nothing about storage, review, versioning, or
experimentation.

### 1.2 Evaluation

The result of running a Question (and, where relevant, a candidate answer) through
LLM-as-judge scoring against a rubric.

- `id`
- `question_id` + `question_version` — evaluates one specific version, never "the
  question" ambiguously
- `rubric_id` / `rubric_version` — which rubric was applied
- `scores` — one entry per rubric dimension (see Section 4)
- `overall_verdict` — pass / fail / needs-review, derived from dimension scores against
  thresholds
- `judge_rationale` — free-text justification per dimension, required (never a bare
  number — see Section 4)
- `reference_answer_used` — whether a reference answer was supplied to the judge
- `evaluation_metadata` — link to metadata record (model, cost, latency, prompt version)
- `created_at`

An Evaluation is immutable once written. Re-evaluating a question (new rubric version, new
judge model, or after an edit produces a new question version) creates a **new**
Evaluation record rather than overwriting — this is what makes experimentation (Section 7)
possible: you can compare evaluations of the same question version across judge models or
rubric versions.

### 1.3 Review (SME feedback)

A human decision on a specific Question version.

- `id`
- `question_id` + `question_version` — the exact version reviewed
- `reviewer_id`
- `decision` — `approve`, `reject`, `edit`
- `feedback` — structured (see Section 5.2), not a free-text blob
- `linked_new_version` — if decision is `edit`, points to the version created by this
  review
- `created_at`

### 1.4 Document (RAG)

A source document used for document-grounded generation.

- `id`
- `title`, `original_filename`
- `status` — `ingested`, `chunked`, `embedded`, `ready`, `failed`
- `chunk_count`
- `topic` / `tags` — inherited by questions generated from it, for consistent filtering
- `created_at`

Chunks are not a separate entity in this design's vocabulary at the product level — they
are an internal detail of retrieval. What matters at the product/entity level is that a
Question generated from a Document can trace back to **which chunks** were used
(captured in generation metadata's `rag_usage`, Section 6), not just which document.

### 1.5 Experiment

A structured comparison run: same generation/evaluation task, executed across two or more
variants (models, prompt versions, or RAG vs. non-RAG), so results are comparable.

- `id`, `name`, `hypothesis` — what's being tested, in plain language
- `variants` — list of configurations under comparison (e.g. `model=A` vs `model=B`, or
  `prompt_v1` vs `prompt_v2`, or `rag=on` vs `rag=off`), holding everything else constant
- `runs` — each run links to the Questions and Evaluations it produced, tagged by variant
- `metrics_summary` — aggregated comparison (see Section 7)
- `status` — `running`, `complete`
- `created_at`

An Experiment does not generate new entity types — it's an organizing/aggregation layer
over Questions and Evaluations that already exist, tagged by which variant produced them.

### 1.6 Status — the lifecycle field

`status` on a Question tracks where it sits in the pipeline. It is one field, one
source of truth for "is this question usable":

```
generated -> auto_evaluated -> pending_review -> approved
                             \-> rejected
                             \-> edited (new version created, old version archived)
```

- `generated`: written immediately after LLM generation, before any evaluation.
- `auto_evaluated`: has at least one Evaluation record; may be auto-filtered here (Section
  2) before ever reaching a human.
- `pending_review`: passed auto-evaluation threshold, queued for SME.
- `approved` / `rejected` / `edited`: terminal-ish SME decision. `edited` is terminal for
  *this version* — the new version it links to re-enters the lifecycle at `generated` (or
  skips straight to `pending_review` if the edit itself is treated as SME-authored and
  trusted — a policy choice, not a structural one).

### 1.7 Versioning

An edit **never overwrites**. Editing a question creates a new record with the same `id`,
`version` incremented, and `parent_id` pointing at the version it was edited from. The
original version is retained, marked superseded, and remains queryable.

Why: the original (pre-edit) version is training/analysis signal in its own right — it
tells you exactly what the LLM got wrong and what an SME changed, which is the raw
material for improving prompts (Section 2). In-place edits destroy that signal. Versioning
also gives a clean audit trail (who changed what, when, why) and lets Evaluations and
Reviews attach to an exact version instead of an ambiguous "the question" that silently
changed underneath them.

The **dataset consumers care about** (e.g. "give me the approved MCQ set for topic X") is
always defined as "latest approved version per lineage `id`," not "every row in the
table."

---

## 2. System Lifecycle

```
 Generation
     |
     v
 Auto Evaluation  ---- fails threshold ----> rejected (never reaches SME)
     |
     | passes threshold
     v
 SME Review  ----------- approve -----------> Storage (approved pool)
     |  \
     |   \--- reject -----------------------> Storage (rejected pool, with feedback)
     |
      \--- edit -----> new version -----> re-enters Auto Evaluation
                                            (or pending_review, per policy)
     v
 Storage (all versions, all decisions, retained)
     |
     v
 Experimentation (compare variants using the approved pool + evaluation history)
     |
     v
 Improvement (prompt/rubric/model changes informed by rejection & edit patterns)
     |
     +----------------------------> feeds back into Generation
```

**How bad questions are filtered — two gates, cheap-first:**
1. **Auto-evaluation gate** (cheap, fast, no human time): every generated question is
   scored against the rubric immediately. Questions failing a hard threshold (e.g.
   factually wrong per the judge, malformed structure, duplicate) are marked `rejected`
   automatically and never consume SME attention. This is a filter, not a final verdict —
   thresholds are deliberately conservative (only reject what's clearly bad) because
   auto-eval can be wrong; anything ambiguous is routed to SME instead of auto-rejected.
2. **SME gate** (expensive, authoritative): only questions that clear the auto-eval bar
   reach a human. The SME decision is final for that version.

**How good questions are reused:** the "approved pool" — latest-approved-version per
lineage — is the canonical dataset. It is what experimentation reads from, what a
downstream consumer (quiz builder, exam generator, etc.) would draw from, and what
deduplication checks new generations against (Section on Deduplication below). Approval is
not a one-time gate that's forgotten — approved questions remain first-class, reusable
assets, not just an audit log entry.

**Deduplication** sits inside the Generation step, not as a separate lifecycle stage:
before a newly generated question is persisted, its embedding is compared against the
approved pool (and optionally the pending pool) within the same topic scope. Near-duplicates
above a similarity threshold are flagged at creation time — either auto-discarded or
surfaced to the SME as "similar to existing question X" during review, so the SME decides
whether it's true redundancy or a legitimately different question. This keeps the dataset
diverse without silently losing edge cases a threshold got wrong.

**How the system improves over time — the feedback loop is data, not vibes:**
- **Rejection patterns** are aggregated by topic, question type, prompt version, and
  model. A prompt version with a rejection rate spiking on a particular topic or failure
  mode (e.g. "distractors too obviously wrong" on MCQ) is a concrete, measurable signal to
  revise that prompt — not a hunch.
- **Edit patterns** are even richer than rejections: an edit shows *exactly* what was wrong
  and what "right" looks like (the new version). Diffing original vs. edited versions at
  scale surfaces systematic LLM weaknesses (e.g. "explanations are consistently too short,"
  "fourth distractor is always implausible") that individual reviews wouldn't surface.
- **Auto-eval vs. SME agreement** is tracked per rubric dimension. If the judge
  consistently disagrees with SME decisions on a dimension, that dimension's rubric wording
  or the judge prompt is the thing to fix — this is how the auto-eval gate itself gets
  more trustworthy over time, not just the generation prompts.
- Each of these signals becomes an input to a new **prompt version** or **rubric version**,
  which becomes a new **Experiment variant**, which is measured against the old one before
  being promoted to default. Improvement is versioned and measured, same as questions are.

---

## 3. Question Design Standards

### 3.1 MCQ

**What makes a good MCQ:**
- Exactly one unambiguously correct option; distractors are plausible enough to require
  real knowledge to eliminate, not obviously silly or answerable by elimination-by-length
  or elimination-by-grammar.
- Stem is self-contained — answerable without seeing the options (a well-formed stem
  reads like a real question, not a fragment that only makes sense once you see option A).
- Distractors are *homogeneous* in style, length, and specificity with the correct answer
  — a stylistic outlier is a free tell.
- Exactly one clearly testable concept per question (no "which of the following are all
  true" compound trick questions unless that's an explicit, deliberate design).
- Explanation field justifies the correct answer *and*, ideally, why the strongest
  distractor is wrong — this doubles as judge context and as SME review aid.

**Common LLM failure modes:**
- **Length/specificity tell**: correct answer is noticeably longer or more detailed than
  distractors.
- **All-of-the-above / none-of-the-above overuse**: statistically these are
  disproportionately used as filler by LLMs, and often disproportionately correct too,
  which trains test-takers to pattern-match rather than know the material.
- **Distractor implausibility**: at least one distractor is trivially wrong (off-topic,
  factually absurd), effectively making it a 3-option or 2-option question.
- **Ambiguous or multi-correct**: two options are both defensible depending on
  interpretation, especially on subjective or fast-evolving topics.
- **Stem leakage**: the stem itself hints at or contains the answer.

### 3.2 True/False

**What makes a good True/False question:**
- The statement tests a single, specific, unambiguous fact or relationship — not a
  compound statement where one clause is true and another false (that just tests reading
  comprehension of the sentence, not the underlying knowledge).
- Avoids absolute qualifiers ("always," "never") *unless* the absolute is itself precisely
  what's being tested — LLMs and humans both over-index on "absolute language = probably
  false," so overusing that pattern makes the question trivially gameable.
- False statements are false due to a specific, identifiable error, not vague wrongness —
  this is what makes the explanation field meaningful and gradeable.

**Common LLM failure modes:**
- Compound statements (true+false clauses glued together) presented as single T/F items.
- Trivial or vacuously true/false statements (too easy to be useful).
- Statement is true/false depending on unstated context or interpretation.
- Systematic true/false imbalance across a generated batch (the model defaults to
  "true" more often than "false," making the answer key guessable without reading the
  question — must be checked at the batch/dataset level, not just per-question).

### 3.3 Fill in the Blank

**What makes a good Fill-in-the-Blank question:**
- Exactly one blank, testing one specific, unambiguous term or short phrase — not a blank
  that could be correctly filled by multiple different valid words.
- Surrounding context in the stem constrains the answer enough that it's gradeable (not
  "The capital of ___ is important" — too open-ended).
- Acceptable-answer list captures reasonable variants (synonyms, singular/plural,
  common abbreviations) up front, rather than relying on the SME to catch every valid
  phrasing during grading.
- Blank position is not at the very start of the stem (loses context that constrains the
  answer) and not trivially inferable from sentence structure alone (e.g. blank preceded
  by "a" vs "an" leaking whether the answer starts with a vowel).

**Common LLM failure modes:**
- Multiple valid answers exist but only one is captured, causing false negatives at grading
  time.
- Blank is under-constrained (many plausible fills) or over-constrained to the point the
  answer is copy-pasted from adjacent stem text.
- Answer requires exact phrasing/formatting the model didn't anticipate (case, units,
  punctuation) — this is an evaluation-design problem as much as a generation problem
  (Section 4.3 handles the grading side).

---

## 4. Evaluation Design

### 4.1 Rubric structure

A rubric is a versioned, named set of **dimensions**, each independently scored. Dimensions
are shared across a question type (all MCQs are judged on the same dimension set) so scores
are comparable across questions, prompts, and models.

Baseline dimensions applicable to (almost) every type:
- **Correctness** — is the marked answer actually correct / factually accurate.
- **Clarity** — is the stem unambiguous and self-contained.
- **Difficulty calibration** — does actual difficulty match the requested difficulty
  level.
- **Distractor/option quality** *(MCQ only)* — are wrong options plausible and
  homogeneous.
- **Explanation quality** — does the explanation actually justify the answer, not just
  restate it.
- **Groundedness** *(document-based generation only)* — is the question answerable from,
  and faithful to, the source document (not the model's outside knowledge).

Each dimension gets: a **score** (small discrete scale, e.g. 1–4, not open-ended 1–10 —
discrete scales reduce judge inconsistency and are easier to threshold on), and a
**required rationale string** — the judge must justify the score in text. A bare number
with no rationale is not trusted output; rationale is what makes judge errors auditable by
an SME and is what makes rejection-pattern analysis (Section 2) possible at all.

### 4.2 Scoring system

- Per-dimension scores roll up into an `overall_verdict` via explicit, documented
  thresholds (e.g. "any dimension below 2/4, or Correctness below 3/4 → reject"). The
  rule is a design decision that lives in the rubric definition, not a hidden heuristic —
  it must be inspectable and tunable.
- Thresholds are intentionally asymmetric: correctness has a much higher bar than, say,
  difficulty calibration — a wrong answer is disqualifying, a slightly-too-easy question is
  not.
- Judge robustness safeguards (structural, not tied to any provider):
  - **Structured output required** — the judge must return per-dimension scores +
    rationale in a fixed shape; unparseable output is treated as an evaluation failure,
    not silently coerced into a passing score.
  - **Position bias guard** — for MCQ, the correct option's position is randomized/known
    not to correlate with judge behavior; if the judge is also asked to independently
    verify the answer key, option order presented to the judge should be varied across
    runs, not fixed.
  - **Verbosity bias guard** — explanation quality is scored against a rubric definition
    ("justifies the answer with a specific reason"), not "is longer than X words," so a
    padded explanation doesn't automatically score higher.
  - **Self-preference guard** — where practical, the judge model differs from the
    generation model, or is explicitly instructed to evaluate on stated criteria only, not
    stylistic preference.

### 4.3 Differences per question type

- **MCQ**: unique dimension for distractor quality; correctness check includes verifying
  the marked-correct option is actually correct *and* that no other option is arguably
  also correct.
- **True/False**: correctness check must verify the statement's truth value independent
  of the label the generator assigned (a naive judge that just "trusts" the generation is
  worthless — it must re-derive the answer, ideally against a reference or the source
  document).
- **Fill in the Blank**: adds an **answer-key completeness** check — does the accepted-answer
  list plausibly cover reasonable valid phrasings, since this is the type most prone to
  false-negative grading at consumption time (Section 3.3).
- **Groundedness** only applies (and is only meaningful) when `source = document`; for
  topic-based generation it's omitted from the rubric rather than scored as N/A, to avoid
  polluting aggregate metrics with a non-applicable dimension.

### 4.4 Reference answers

Where available, a reference answer (SME-authored or sourced from the document) is passed
to the judge alongside the question. This substantially improves judge reliability on
correctness — it converts "does the judge independently know the right answer" (unreliable
for niche/updated/specialized topics) into "does the generated answer match a known-good
answer" (a much easier and more reliable judgment). Reference answers are optional at the
data-model level (not every topic has one) but strongly preferred, and their presence is
recorded per-Evaluation (`reference_answer_used`) so evaluation quality is itself
inspectable — a batch of evaluations run without references is a signal to weight those
results more cautiously.

---

## 5. SME Review System

### 5.1 Review types

- **Approve**: question is correct and dataset-ready as-is. No payload change. Question
  status moves to `approved`.
- **Reject**: question should not enter the dataset. Requires structured feedback (5.2) —
  a reject with no reason is not useful for the improvement loop (Section 2) and is not
  allowed by design.
- **Edit**: question is close but needs a correction. The SME modifies the payload; this
  produces a new version (1.7), not an in-place change. The original is preserved and
  linked. The new version's `created_by` is the reviewer, and it's tagged as SME-originated
  so downstream consumers and metrics can distinguish "LLM-generated, human-approved" from
  "human-authored/human-corrected" — a meaningful distinction for both dataset provenance
  and for measuring how much the LLM is actually getting right unaided.

### 5.2 Feedback structure

Feedback is structured, not a free-text box, so it's aggregable (Section 2's rejection-
pattern analysis depends on this):
- `reason_category` — a fixed taxonomy: e.g. `factually_incorrect`,
  `ambiguous_wording`, `weak_distractors`, `answer_key_error`, `duplicate`,
  `off_topic`, `difficulty_mismatch`, `formatting_issue`, `other`
- `comment` — free-text elaboration, optional but encouraged, especially for `other`
- `severity` — informs whether this instance also warrants flagging the source prompt
  version for review (a single `other` is noise; ten `weak_distractors` on the same prompt
  version is a signal)

Edits additionally capture **what changed**, implicitly, via the version diff (original
payload vs. new payload) — this is not a separate field, it's derivable by comparing the
two versions, which keeps the feedback structure itself lightweight.

### 5.3 Versioning system

Covered in 1.7. The review-specific detail: a Review record always points at the exact
version it evaluated, and an `edit` decision's Review links forward to the version it
produced (`linked_new_version`). This means the full chain — generated version → its
Evaluation(s) → the Review that acted on it → the resulting new version (if edited) → that
version's own Evaluation(s) and Review — is walkable in one direction, start to finish,
for any question lineage. That chain is the audit trail and the improvement-loop dataset at
once.

### 5.4 How SME review improves system quality over time

- **Immediate**: only approved (or approved-after-edit) questions enter the reusable pool
  — SME review is the final correctness gate no automated system fully replaces.
- **Aggregate, per-prompt-version**: rejection/edit rates broken down by prompt version and
  reason category tell you precisely which prompt is underperforming and *how* — not just
  "quality is bad" but "this prompt version produces weak distractors 30% of the time,"
  which is directly actionable.
- **Judge calibration**: SME decisions are the ground truth against which auto-evaluation
  is measured (Section 2, "auto-eval vs SME agreement"). Systematic disagreement is a
  rubric or judge-prompt bug, and SME review is what surfaces it.
- **Training/reference material**: SME-edited versions are, over time, a growing set of
  human-verified "gold" examples — useful as few-shot examples in generation prompts, as
  reference answers for evaluation, and as a held-out sample for testing new prompt/model
  variants before wider rollout.

### 5.5 Building a high-quality dataset over time

The dataset is not "everything ever generated" — it is explicitly "latest approved version
per lineage," continuously curated as prompts and models improve. Two consequences follow:
- Old approved questions are not immune from re-evaluation: as rubrics or judge models
  improve, previously-approved questions can be re-scored and re-flagged for SME
  re-review, so quality bar increases apply retroactively rather than only to new
  generations.
- Dataset quality is a measured trend, not a one-time claim: approval rate, average rubric
  scores, and rejection-reason distribution over time are the metrics that show whether the
  improvement loop (Section 2) is actually working, per Section 7's experimentation
  metrics.

---

## 6. Metadata Strategy

Every LLM or embedding operation — generation, evaluation/judging, embedding for dedup or
retrieval — logs a metadata record. No silent calls, ever; if an operation can't log
metadata (e.g. the logging call itself fails), the operation is treated as failed, not
silently accepted.

**What is tracked, and why:**

- **Model used** (provider + model identifier + version/snapshot if the provider exposes
  one). *Why:* model behavior drifts across versions even under the same name; without
  this, "why did quality change last week" is unanswerable, and experimentation (Section 7)
  has no way to attribute results to a specific variant.
- **Prompt version**. *Why:* this is the other half of attribution — a quality change is
  either a model change or a prompt change (or both); without tracking both independently
  you can't isolate which one moved the needle, and you can't reproduce a past result.
- **Tokens (input/output)**. *Why:* direct input to cost calculation, and a leading
  indicator of prompt bloat or runaway context — a prompt version whose token count creeps
  up over revisions is worth a second look even before cost becomes a problem.
- **Latency**. *Why:* generation/evaluation is often on a human-facing or human-in-the-loop
  path (SME waiting on eval results); latency regressions are a UX issue, and per-model /
  per-prompt-version latency is a real input to model/prompt selection, not just a
  monitoring afterthought.
- **Cost** (computed from tokens + provider rate). *Why:* the system is explicitly designed
  to run at zero cost to the owner in its public-demo form (visitor-supplied keys), which
  makes *visible, accurate, per-call cost* a product requirement, not just an internal
  metric — a visitor needs to see what their own key is being spent on. It's also the
  primary signal for Section 7's cost-vs-quality tradeoff analysis.
- **RAG usage** (`doc_id`, chunk identifiers actually used). *Why:* traceability — a
  document-grounded question must be able to point at exactly which source material
  produced it, both for groundedness evaluation (Section 4.3) and so an SME reviewing a
  document-based question can go check the source directly instead of taking the model's
  word for it.
- **SME decisions** (as Review records, Section 5, which are themselves metadata about a
  human operation rather than an LLM one). *Why:* this is the ground truth the entire
  improvement loop (Section 2) is built on; without capturing *who* decided *what* and
  *why*, in structured form, at the exact version level, none of the aggregate analysis in
  Sections 2 and 5 is possible.

The unifying principle: metadata is not observability bolted on after the fact — it is the
raw material the improvement loop (Section 2) and experimentation (Section 7) run on.
Anything not logged here is a question the system will not be able to answer later.

---

## 7. Experimentation Strategy

### 7.1 What gets compared

- **Models** — same prompt, same question type/topic, different generation or judge model.
- **Prompts** — same model, different prompt version (wording, few-shot examples, added
  constraints).
- **Pipelines** — RAG-grounded vs. topic-only generation for the same topic; different
  rubric versions scoring the same question set; different retrieval strategies (chunk
  count, chunking granularity) at the RAG stage.

Only one axis should vary per Experiment (Section 1.5) — comparing model A/prompt-v1
against model B/prompt-v2 conflates two variables and produces an uninterpretable result.
Where multiple axes genuinely need testing, that's multiple Experiments, not one.

### 7.2 What metrics matter

- **Quality**: approval rate (SME), average rubric score per dimension, auto-eval pass
  rate, rejection-reason distribution (does variant B reduce `weak_distractors` rate vs.
  variant A specifically, or just move the problem to a different category).
- **Agreement**: auto-eval vs. SME agreement rate — a variant that scores well on
  auto-eval but doesn't hold up under SME review is not actually better, it's just gaming
  the cheap gate.
- **Cost**: total and per-question cost (generation + evaluation combined, since a
  cheaper-but-worse model may need more regeneration/review cycles to reach the same
  approved output).
- **Latency**: per-question generation + evaluation time, relevant wherever there's a
  human waiting synchronously.
- **Diversity**: near-duplicate rate within a batch (a variant producing more repetitive
  questions is worse even if individual-question quality scores look fine).
- **Groundedness** (RAG-specific): fraction of document-based questions that pass the
  groundedness dimension, and whether retrieval changes (chunk size/count) move that
  number independent of the generation model/prompt.

The composite judgment an Experiment should ultimately support is **quality per unit
cost** — a marginally-better model at several times the cost is not automatically the
right default; that tradeoff should be visible, not implicit.

### 7.3 How comparison works structurally

Every run within an Experiment produces ordinary Questions and Evaluations, tagged with
their variant. Aggregation is a read-time computation over existing entities (group by
variant, compute the metrics above) — Experiments do not require a separate parallel data
model for results, which keeps this consistent with Section 1's principle of one entity
shape reused everywhere. A "winning" variant is promoted by updating which prompt
version / model / pipeline config is the *default* for new generation — the experiment
record itself remains as the evidence trail for why.

---

## 8. Future Extensions

The system is designed so **Essay, Matching, and Ordering** slot in without touching
storage, review, versioning, or experimentation — only three things change per new type:

1. **A new payload shape** under the `type` discriminator (Section 1.1). E.g.:
   - **Essay**: `prompt_text`, `model_answer` or `key_points` (list of things a good
     answer must cover), `word_limit`.
   - **Matching**: `left_items` / `right_items` (lists), `correct_pairs`.
   - **Ordering**: `items` (list, generation-time order scrambled from a `correct_order`).
2. **A new generator** that produces that payload shape (same generation service pattern,
   new prompt template + parser).
3. **New/extended rubric dimensions** specific to that type, since "correctness" for an
   essay is fundamentally graded-against-key-points rather than exact-match:
   - **Essay**: needs a rubric dimension for key-point coverage (does the model answer hit
     the required points) and is the one type where auto-evaluation itself is closer to
     free-response grading than answer-checking — likely needs its own judge prompt
     designed for partial-credit, multi-point scoring rather than the discrete-scale
     dimensions used elsewhere. This is the type most likely to need heavier SME review
     weighting relative to auto-eval, since free-response correctness judgment is exactly
     where judge failure modes (Section 4.2) are hardest to guard against.
   - **Matching / Ordering**: correctness is structurally checkable (pair/order either
     matches the key or doesn't), so these are actually *simpler* to auto-evaluate than
     MCQ — the harder design question is generation quality (are the items genuinely
     related/orderable, not trivially guessable from list position or length).

Everything else — status lifecycle, versioning, Review structure, metadata logging,
Experiment comparison — is defined generically over "a Question" and requires zero changes
when a new type is added. This is the direct payoff of Section 1.1's type-discriminated
model over per-type tables: adding a type is additive (new payload + new generator/judge
pair), never a migration of the existing dataset or a change to how review/versioning/
experimentation work.
