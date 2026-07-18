# Design Decisions (why X over Y)

Add an entry as you make each decision. Keep each to 3-5 sentences: the choice, the
alternative, and the reason. This is the highest-signal doc for interviewers.

- Provider abstraction over hardcoding a vendor -> why: `services/` code only ever
  imports the `LLMProvider` Protocol (`llm/base.py`), never the `groq` SDK directly.
  Swapping or adding a provider (OpenAI, Anthropic, a local model) is then a new
  `llm/*_provider.py` file plus a `registry.py` entry — zero changes to generation,
  evaluation, or prompt code.
- LLM-as-judge over human-only evaluation -> why:
- Rubric scoring over a raw 1-10 score -> why:
- Reference answers included in evaluation -> why:
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