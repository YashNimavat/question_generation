# Design Decisions (why X over Y)

Add an entry as you make each decision. Keep each to 3-5 sentences: the choice, the
alternative, and the reason. This is the highest-signal doc for interviewers.

- Provider abstraction over hardcoding a vendor -> why: `services/` code only ever
  imports the `LLMProvider` Protocol (`llm/base.py`), never the `groq` SDK directly.
  Swapping or adding a provider (OpenAI, Anthropic, a local model) is then a new
  `llm/*_provider.py` file plus a `registry.py` entry — zero changes to generation,
  evaluation, or prompt code.
- LLM-as-judge over human-only evaluation -> why: SME time is the scarcest resource in the
  pipeline (`SYSTEM_DESIGN.md` §2's two-gate model), so a cheap automated pass filters out
  the clearly-bad questions (malformed, factually wrong) before anything reaches a human,
  and only ambiguous/borderline cases consume SME attention. Auto-eval is deliberately a
  filter, not a final verdict — thresholds stay conservative (Slice 4's rule only
  auto-rejects on `fail`, everything else routes onward).
- Rubric scoring over a raw 1-10 score -> why: a discrete 1-4 scale per named dimension
  (with a required rationale) is far more consistent judge-to-judge and run-to-run than an
  open-ended 1-10, and the per-dimension breakdown is what makes rejection-pattern analysis
  (`SYSTEM_DESIGN.md` §2, "weak distractors 30% of the time on prompt X") possible at all —
  a single scalar score can't be attributed to a specific failure mode.
- Reference answers included in evaluation -> why: for a judge without a reference answer,
  "is this correct" collapses to "does the judge happen to know this niche/updated fact,"
  which is unreliable. An optional reference answer converts that into "does it match a
  known-good answer" — a strictly easier and more reliable judgment — so Slice 4 supports it
  as an optional param even though most evaluations run without one for now.
- SQLite for MVP over Postgres -> why:
- Streamlit-only MVP over Streamlit+FastAPI -> why:
- Type-discriminated Question model over separate tables per type -> why:
- Versioning edited questions (new version linked to original) over in-place edits -> why:
- Embedding-based deduplication over exact-match -> why:
- Visitor-supplied API keys over owner-funded demo -> why:

## Slice 1

- **MCQ options as a sub-model**: used a proper `McqOption` (id/text/is_correct) 
  nested model with a `model_validator` enforcing exactly one correct answer, 
  instead of loose dicts — both design docs already agreed on the shape, 
  so there was nothing left to keep flexible.

- **DB connections**: one short-lived sqlite3 connection per repository call, 
  not a shared long-lived connection — Streamlit reruns the script on every 
  interaction and can use multiple threads, so a shared connection risked 
  thread-safety issues.

- **Schema**: a single schema.sql applied with CREATE TABLE IF NOT EXISTS, 
  no migration tool — there's no deployed data yet to migrate. Revisit this 
  at Slice G2 (Postgres migration).

## Slice 2

- **`config/secrets.toml` + a hand-rolled `tomllib` loader, over `pydantic-settings`/`.env`**:
  the owner's own Groq key only needs to exist for local dev/testing (visitors bring
  their own key later, per `docs/TECH_DECISIONS.md`), so a single gitignored TOML file
  with a committed `secrets.example.toml` template is enough — no new dependency, and it
  matches the `config/secrets.example.toml` naming already used in
  `docs/TECH_ARCHITECTURE.md`'s target folder structure.

- **`GroqProvider` takes an injectable `client`**: the constructor accepts an optional
  pre-built `Groq` client so tests can pass a fake object shaped like the SDK's
  `chat.completions.create(...)` response instead of hitting the network or pulling in a
  mocking library — consistent with the rest of the test suite, which uses plain
  fakes/factories rather than `unittest.mock`.

- **Retry-once-then-fail on malformed generation output**: matches
  `docs/TECH_ARCHITECTURE.md` §3.1 — one corrective follow-up turn is appended to the
  conversation and replayed; if that also fails to parse/validate, `generate_mcq` raises
  `GenerationError` and persists no `Question` row, but every attempt (including failed
  ones) still gets its own `metadata_logs` row, since a parse failure is not a logging
  failure.

- **Hardcoded per-model Groq pricing table** (`llm/groq_provider.py`): cost is computed
  from a `$/1M tokens` dict the provider owns internally, per
  `docs/TECH_ARCHITECTURE.md` §9.1 ("cost computed per-provider"). An unrecognized model
  raises immediately rather than silently reporting `cost_usd=0` — a missing rate is a
  bug to fix, not a value to guess.

  - Streamlit only adds the entry script's own directory to sys.path, not the 
  repo root — so imports like `from core...` failed at runtime despite 
  passing unit tests. Fixed with an explicit repo-root path insert at the 
  top of each page.

## Slice 4

- **Rubric as a hardcoded Python constant (`core/rubric.py`), not a file-loading
  mechanism**: only one rubric (`rubric_mcq`/`v1`) exists so far, so a `Rubric`/
  `RubricDimension` Pydantic constant plus a small `(question_type, id, version) -> Rubric`
  dict lookup is enough — same "no premature abstraction" call as Slice 2's hand-rolled
  secrets loader. Per-level scoring guide text lives only in `prompts/judge_mcq_v1.txt`
  (not duplicated into the rubric model), so there's a single place to edit judge wording.

- **Correctness-weighted, asymmetric verdict threshold**: `correctness < 3` always fails
  regardless of other dimensions; any other dimension at `1` also fails; a `2` elsewhere
  (with correctness clear) is `needs_review`, not an auto-fail. Matches
  `SYSTEM_DESIGN.md` §4.2's explicit call for asymmetric thresholds — a wrong answer is
  disqualifying, a slightly-miscalibrated difficulty is not, and it keeps the auto-eval
  gate conservative (only clearly-bad questions get auto-rejected; everything else reaches
  an SME).

- **Separate `default_judge_model` from `default_llm_model`**: a self-preference guard
  (`SYSTEM_DESIGN.md` §4.2) — the judge defaults to a different Groq model than the one
  used for generation, independently overridable per call, rather than reusing the
  generation model by default.

- **Optional `reference_answer` param, not yet a stored/first-class entity**: `evaluate()`
  accepts a plain `str | None` passed straight through from the caller (Streamlit text
  box) rather than persisting it anywhere — `SYSTEM_DESIGN.md` doesn't model reference
  answers as their own entity yet, only as a per-Evaluation `reference_answer_used` flag,
  so there's nothing to store beyond that flag at this slice.