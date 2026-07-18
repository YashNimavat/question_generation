# Technical Architecture — Question Intelligence System

Reference design. This document maps the product design (`docs/SYSTEM_DESIGN.md`) onto a
concrete technical implementation. It describes the **full target architecture**,
including Phase 2/3 material that is explicitly not built yet.

**Scope discipline:** `docs/TECH_DECISIONS.md` is the locked source of truth for what is
actually built in Phase 1 (MVP). Where this document describes something deferred —
FastAPI, hosted Postgres, a hosted vector store, LangSmith/RAGAS — it is marked
**[Phase 2]** / **[Phase 3]** / **[reference only]** and is not to be scaffolded during
MVP work. If this document and `TECH_DECISIONS.md` ever conflict on what Phase 1 includes,
`TECH_DECISIONS.md` wins.

---

## 1. Architecture

### 1.1 Layering principle

Every capability is a **service function**, independent of how it's invoked. The UI layer
(Streamlit now, optionally a REST API later) is a thin caller — it never contains business
logic, never talks to a provider SDK directly, and never issues raw SQL.

```
 UI layer            Streamlit pages (Phase 1)   |  FastAPI routers (Phase 2, same services)
                                    |                                  |
                                    v                                  v
 Service layer       services/generation, evaluation, review, experiment, ingestion
                      (pure business logic; UI-agnostic; fully testable without a UI)
                                    |
        +---------------------------+----------------------------+
        v                           v                            v
 Provider layer       llm/ (LLMProvider)   embeddings/ (EmbeddingProvider)   rag/ (VectorStore)
        |                           |                            |
        v                           v                            v
   Groq API                   Cohere API                  chromadb (in-process)

 Cross-cutting        metadata/  — every provider call logs model, tokens, latency,
                       cost, prompt_version, rag_usage
                       db/       — repository layer, the only code that touches SQLite
```

This is why Phase 2's FastAPI layer is additive, not a rewrite: it is a second thin caller
over the same `services/` functions, exactly parallel to how Streamlit calls them today.

### 1.2 Components and boundaries

| Component | Owns | Never does |
|---|---|---|
| `app/` (Streamlit) | Page layout, forms, session state, calling services | Business logic, provider calls, SQL |
| `services/` | Orchestration: validate input, call provider(s), call repository, log metadata | Knowing which concrete provider/DB is in use |
| `llm/`, `embeddings/`, `rag/` | Provider-specific request/response translation into a common interface | Business rules (thresholds, status transitions) |
| `metadata/` | Recording every provider call's cost/latency/usage | Deciding pass/fail (that's the evaluation service, using metadata as input) |
| `db/` | Schema, migrations, repository CRUD, versioning mechanics | Business rules beyond referential integrity |
| `core/` | Pydantic domain models, enums, status transitions | I/O of any kind |

### 1.3 Interaction flow — end to end (topic-based MCQ, Phase 1)

```
Streamlit page "Generate"
  -> services.generation.generate_mcq(topic, difficulty, model_config)
       -> llm.LLMProvider.generate(prompt from prompts/mcq_v1.txt)
       -> metadata.log_call(...)               # tokens, cost, latency, prompt_version
       -> parse + validate LLM output into core.MCQQuestion
       -> services.dedup.check_similarity(vector, topic)   [Slice 8]
       -> db.questions_repo.insert(question, status="generated")
  <- returns Question to UI
Streamlit page "Generate" (auto-triggers or user clicks "Evaluate")
  -> services.evaluation.evaluate(question_id)
       -> llm.LLMProvider.generate(judge prompt + rubric + question)
       -> metadata.log_call(...)
       -> parse structured judge output -> core.Evaluation
       -> db.evaluations_repo.insert(...)
       -> db.questions_repo.update_status(question_id, "auto_evaluated" | "rejected")
  <- returns Evaluation to UI
Streamlit page "SME Review"
  -> services.review.submit_review(question_id, version, decision, feedback)
       -> if decision == "edit": db.questions_repo.insert_new_version(...)
       -> db.reviews_repo.insert(...)
       -> db.questions_repo.update_status(...)
  <- returns updated Question + Review to UI
```

Document-based generation and RAG retrieval insert one step between "form submit" and
"LLMProvider.generate": `rag.retrieval.get_relevant_chunks(topic, document_id)`, whose
output (chunk texts + chunk ids) is folded into the prompt and recorded in
`metadata.rag_usage`.

---

## 2. Folder Structure

### 2.1 Phase 1 (build this now — matches `docs/TECH_DECISIONS.md`)

```
question_intelligence/
  app/
    main.py                    # Streamlit entry point, page router
    pages/
      1_generate.py            # topic + document based generation
      2_questions.py           # browse/filter stored questions
      3_evaluate.py            # trigger + view evaluations
      4_review.py              # SME review dashboard
      5_documents.py           # upload + manage RAG documents      [Slice 6]
      6_experiments.py         # compare model/prompt/RAG variants   [Slice 9]
    components/                # shared Streamlit widgets (question card, score badge)
    state.py                   # session-state helpers (BYO API key handling)

  core/
    models.py                  # Question (discriminated union), Evaluation, Review,
                                # Document, Experiment — Pydantic
    enums.py                   # QuestionType, QuestionStatus, ReviewDecision, Source
    rubric.py                  # Rubric, RubricDimension models

  services/
    generation.py               # generate_mcq / generate_true_false / generate_fill_blank
    evaluation.py                # evaluate(question_id, rubric_id) -> Evaluation
    review.py                    # submit_review(...) incl. versioning
    experiment.py                # run_experiment(...), aggregate_results(...)   [Slice 9]
    ingestion.py                  # ingest_document(...)                          [Slice 6]
    dedup.py                      # check_similarity(...)                         [Slice 8]

  llm/
    base.py                     # LLMProvider Protocol, LLMResult, Message
    groq_provider.py            # concrete implementation
    registry.py                 # config-driven provider selection

  embeddings/
    base.py                     # EmbeddingProvider Protocol, EmbeddingResult
    cohere_provider.py

  rag/
    chunking.py                  # document -> chunks
    vector_store.py               # VectorStore Protocol + chromadb implementation
    retrieval.py                   # top-k retrieval given a query/topic
    grounding.py                    # fold retrieved chunks into a generation prompt

  metadata/
    logger.py                    # log_call(...) — single entry point every provider
                                  # call must go through
    models.py                    # MetadataRecord

  db/
    schema.sql                   # SQLite DDL (see Section 4)
    connection.py                 # connection/session management
    repositories/
      questions_repo.py
      evaluations_repo.py
      reviews_repo.py
      documents_repo.py
      experiments_repo.py
      metadata_repo.py

  prompts/
    mcq_v1.txt
    true_false_v1.txt
    fill_blank_v1.txt
    judge_mcq_v1.txt
    judge_true_false_v1.txt
    judge_fill_blank_v1.txt

  config/
    settings.py                  # non-secret config (default model, token caps)
    secrets.example.toml         # template only; real secrets never committed

  tests/
    services/
    llm/
    embeddings/
    rag/
    db/

  docs/
  pyproject.toml
  .gitignore
```

### 2.2 Phase 2 addition — `api/` **[Phase 2, reference only]**

```
  api/
    main.py                     # FastAPI app
    routers/
      questions.py               # thin wrappers around services.generation / db reads
      evaluations.py             # wraps services.evaluation
      reviews.py                 # wraps services.review
      documents.py                # wraps services.ingestion
      experiments.py               # wraps services.experiment
    schemas.py                  # request/response models (can mirror core/ models)
    deps.py                     # auth/rate-limit dependencies, once needed
```

`api/` contains **no business logic** — every router handler is a direct call into an
existing `services/` function. This is the payoff of the layering in Section 1.1: adding
this folder is the entire Phase 2 API migration.

---

## 3. Core Modules

### 3.1 Generation engine (`services/generation.py`)

Responsibilities: build the prompt (topic-only or RAG-grounded), call `LLMProvider`,
parse+validate the structured output into the correct `core.models` type, run dedup check,
persist, log metadata. One function per question type (`generate_mcq`,
`generate_true_false`, `generate_fill_blank`) sharing a common internal pipeline
(`_generate(question_type, ...)`) so adding Essay/Matching/Ordering later means adding a
new thin wrapper + prompt + parser, not a new pipeline.

Output parsing is strict: the LLM is prompted for a fixed JSON shape; a response that
fails schema validation is retried once with an error-correction follow-up prompt, then
surfaced as a generation failure (logged, not silently discarded) rather than persisted as
a malformed question.

### 3.2 RAG pipeline (`rag/`)

See Section 6 for the full pipeline. Module boundary: `chunking.py` and `vector_store.py`
have zero knowledge of questions/evaluations — they operate on raw text and vectors only.
`retrieval.py` and `grounding.py` are what `services/generation.py` and
`services/ingestion.py` actually import.

### 3.3 Evaluation engine (`services/evaluation.py`)

Loads the rubric for the question's type, builds the judge prompt (question + rubric +
reference answer if available), calls `LLMProvider`, parses per-dimension structured
scores + rationale, computes `overall_verdict` from the rubric's threshold rules, persists
an `Evaluation`, and updates the question's `status`. See Section 8 for scoring detail.

### 3.4 Metadata system (`metadata/logger.py`)

A single function, `log_call(operation_type, provider, model, prompt_version, usage,
rag_usage=None)`, called by every `llm/` and `embeddings/` invocation site — never called
directly by UI code. Cost is computed inside the provider implementation (each provider
knows its own pricing) and passed through as part of `LLMResult`/`EmbeddingResult`, so
`metadata/` stays provider-agnostic and just persists what it's given.

### 3.5 Experimentation system (`services/experiment.py`) **[Slice 9]**

Runs the same generation/evaluation task across N variant configs (model, prompt version,
or RAG on/off), tagging every produced `Question`/`Evaluation` with the variant. Aggregation
(`aggregate_results`) is a read-time SQL query grouped by variant tag — no separate
results table beyond a thin `experiment_runs` join table (Section 4.5).

### 3.6 SME review system (`services/review.py`)

See Section 9 for full detail. Core responsibility: enforce that `edit` decisions always
go through `questions_repo.insert_new_version` (never `UPDATE` on an existing row) and
that every `Review` row is linked to the exact `(question_id, version)` it acted on.

---

## 4. Database Schema

Phase 1: SQLite, accessed only through `db/repositories/`. Schema is written so a later
move to Postgres (Phase 2, if concurrency demands it) is a connection-string + minor
dialect change, not a redesign — no SQLite-only features (no `ROWID` reliance beyond the
standard integer primary key behavior both engines share).

Composite identity: a question **lineage** is `id`; a specific **version** is
`(id, version)`. All foreign keys from `evaluations` / `reviews` point at the specific
version.

### 4.1 `questions`

| Column | Type | Notes |
|---|---|---|
| `id` | TEXT (UUID) | lineage identity, shared across versions |
| `version` | INTEGER | starts at 1, increments per edit |
| `type` | TEXT | `mcq` \| `true_false` \| `fill_blank` (future types added, not migrated) |
| `status` | TEXT | `generated` \| `auto_evaluated` \| `pending_review` \| `approved` \| `rejected` \| `edited` |
| `stem` | TEXT | |
| `payload` | TEXT (JSON) | type-specific fields (options/correct_answer/answer) — see 4.1.1 |
| `difficulty` | TEXT | |
| `topic` | TEXT | indexed |
| `tags` | TEXT (JSON array) | |
| `source` | TEXT | `topic` \| `document` |
| `document_id` | TEXT (UUID, nullable, FK -> documents.id) | set when `source = document` |
| `parent_id` | TEXT (UUID, nullable) | points at `id` this version; combine with a `parent_version` column for exact lineage |
| `parent_version` | INTEGER (nullable) | |
| `generation_metadata_id` | TEXT (UUID, FK -> metadata_logs.id) | |
| `created_by` | TEXT | `"system"` or reviewer id |
| `created_at` | TEXT (ISO 8601) | |

`PRIMARY KEY (id, version)`. Index on `(topic, status)` and on `(id)` for "give me the
latest version" lookups.

**4.1.1 Payload JSON shape per type** (validated at the Pydantic layer before persistence,
not by the DB):
- `mcq`: `{options: [{id, text, is_correct}], explanation}`
- `true_false`: `{correct_answer: bool, explanation}`
- `fill_blank`: `{accepted_answers: [str], blank_marker, case_sensitive: bool}`

Storing the payload as JSON (rather than a column per possible field across all types)
is what avoids a table-per-type or a wide sparse table — it is the storage-level
expression of the type-discriminated model from `docs/SYSTEM_DESIGN.md` §1.1. All shared
fields (status, versioning, topic, metadata link) stay as real columns since every service
that isn't type-aware (review, versioning, experimentation) needs to query on them
directly.

### 4.2 `evaluations`

| Column | Type | Notes |
|---|---|---|
| `id` | TEXT (UUID) | |
| `question_id` | TEXT | FK -> questions.id |
| `question_version` | INTEGER | FK -> questions.(id, version) |
| `rubric_id` | TEXT | |
| `rubric_version` | TEXT | |
| `scores` | TEXT (JSON) | `{dimension: {score, rationale}}` |
| `overall_verdict` | TEXT | `pass` \| `fail` \| `needs_review` |
| `reference_answer_used` | INTEGER (bool) | |
| `metadata_id` | TEXT (UUID, FK -> metadata_logs.id) | |
| `created_at` | TEXT | |

Immutable — never updated after insert (§ SYSTEM_DESIGN.md 1.2). Index on
`(question_id, question_version)`.

### 4.3 `reviews`

| Column | Type | Notes |
|---|---|---|
| `id` | TEXT (UUID) | |
| `question_id` | TEXT | FK -> questions.id |
| `question_version` | INTEGER | exact version reviewed |
| `reviewer_id` | TEXT | |
| `decision` | TEXT | `approve` \| `reject` \| `edit` |
| `reason_category` | TEXT (nullable) | fixed taxonomy, required when decision != approve |
| `comment` | TEXT (nullable) | |
| `severity` | TEXT (nullable) | |
| `linked_new_version` | INTEGER (nullable) | set when `decision = edit` |
| `created_at` | TEXT | |

Index on `(question_id, question_version)` and on `(reviewer_id)` for reviewer-level
aggregation.

### 4.4 `documents`

| Column | Type | Notes |
|---|---|---|
| `id` | TEXT (UUID) | |
| `title` | TEXT | |
| `original_filename` | TEXT | |
| `status` | TEXT | `ingested` \| `chunked` \| `embedded` \| `ready` \| `failed` |
| `chunk_count` | INTEGER | |
| `topic` | TEXT | |
| `tags` | TEXT (JSON array) | |
| `created_at` | TEXT | |

Chunk text/vectors are **not** in SQLite — they live in the vector store (Section 6.3);
`documents.chunk_count` is denormalized for quick UI display only.

### 4.5 `experiments` + `experiment_runs`

| `experiments` column | Type |
|---|---|
| `id` | TEXT (UUID) |
| `name` | TEXT |
| `hypothesis` | TEXT |
| `variants` | TEXT (JSON) — list of variant configs |
| `status` | TEXT — `running` \| `complete` |
| `created_at` | TEXT |

| `experiment_runs` column | Type | Notes |
|---|---|---|
| `id` | TEXT (UUID) | |
| `experiment_id` | TEXT | FK -> experiments.id |
| `variant_key` | TEXT | which variant config produced this run |
| `question_id` | TEXT | FK -> questions.id |
| `question_version` | INTEGER | |
| `created_at` | TEXT | |

`aggregate_results` joins `experiment_runs` -> `questions` + `evaluations` grouped by
`variant_key`; no separate metrics-storage table needed for Phase 1 scale.

### 4.6 `metadata_logs`

| Column | Type | Notes |
|---|---|---|
| `id` | TEXT (UUID) | |
| `operation_type` | TEXT | `generation` \| `evaluation` \| `embedding` |
| `provider` | TEXT | `groq` \| `cohere` \| future providers |
| `model` | TEXT | |
| `prompt_version` | TEXT (nullable) | |
| `input_tokens` | INTEGER | |
| `output_tokens` | INTEGER | |
| `latency_ms` | REAL | |
| `cost_usd` | REAL | |
| `rag_usage` | TEXT (JSON, nullable) | `{document_id, chunk_ids: [...]}` |
| `created_at` | TEXT | |

Every row in `questions.generation_metadata_id` and `evaluations.metadata_id` points here.
This table is intentionally append-only and is the source for all cost/latency
aggregation in Section 7 (experimentation) and any future monitoring.

---

## 5. API Design **[Phase 2 — reference only, not built in Phase 1]**

Phase 1 has no HTTP layer; Streamlit calls `services/` in-process. The table below is the
target contract for when Phase 2 adds `api/` — each route is a direct passthrough to the
already-existing service function, so this is documentation of a wrapper, not new design
work, when the time comes.

| Method + Path | Wraps | Notes |
|---|---|---|
| `POST /questions/generate` | `services.generation.generate_mcq` / `generate_true_false` / `generate_fill_blank` | body selects `type`, `topic` or `document_id`, `difficulty` |
| `GET /questions` | `db.questions_repo.list` | filter by topic/status/type, paginated |
| `GET /questions/{id}` | `db.questions_repo.get_latest` | latest approved version by default; `?version=` for a specific one |
| `POST /documents` | `services.ingestion.ingest_document` | multipart upload |
| `GET /documents/{id}` | `db.documents_repo.get` | |
| `POST /evaluations` | `services.evaluation.evaluate` | body: `question_id`, `question_version`, optional `rubric_id` |
| `GET /evaluations/{question_id}` | `db.evaluations_repo.list_for_question` | full evaluation history for a lineage |
| `POST /reviews` | `services.review.submit_review` | body: `question_id`, `question_version`, `decision`, `feedback` |
| `GET /reviews/{question_id}` | `db.reviews_repo.list_for_question` | |
| `POST /experiments` | `services.experiment.run_experiment` | body: `variants`, `topic`/`document_id`, sample size |
| `GET /experiments/{id}` | `services.experiment.aggregate_results` | |

Auth/rate-limiting (`api/deps.py`) is out of scope until there is an actual external
consumer — the BYO-key demo model means Phase 1 has no server-side credential to protect.

---

## 6. RAG Pipeline

### 6.1 Ingestion (`services/ingestion.py`)

1. Accept an uploaded file (PDF/DOC), extract raw text.
2. Persist a `documents` row with `status = ingested`.
3. Hand off to chunking synchronously for Phase 1 (no background job queue at this
   scale — a queue is a Phase 3 concern if uploads become large/frequent enough to block
   the UI thread unacceptably).

### 6.2 Chunking (`rag/chunking.py`)

- Fixed-size chunking with overlap (e.g. ~500 tokens, ~15% overlap) as the Phase 1
  default — simplest strategy that gives retrieval enough context per chunk without
  splitting a fact across a chunk boundary too often.
- Chunk boundaries prefer paragraph/sentence breaks over hard token cutoffs where the
  extracted text preserves structure.
- Each chunk keeps a back-reference (`document_id`, `chunk_index`, char offsets) so a
  retrieved chunk can be traced back to its exact source location for SME verification
  (§ SYSTEM_DESIGN.md 1.4, 5.5).
- Chunking strategy is swappable behind a single function signature
  (`chunk(text) -> list[Chunk]`) so a smarter strategy (semantic chunking) can replace it
  later without touching ingestion or retrieval callers.

### 6.3 Embedding + storage (`embeddings/`, `rag/vector_store.py`)

- Chunks are embedded via `EmbeddingProvider.embed(texts, model)` (Cohere first).
- Vectors are stored via a `VectorStore` Protocol (`add(ids, vectors, metadata)`,
  `query(vector, top_k, filter)`), backed by **chromadb running in-process** for Phase 1
  (matches `TECH_DECISIONS.md` — no hosted vector store until corpus size or hosting
  requires it).
- Document status moves `chunked -> embedded -> ready` as each stage completes; a failure
  at any stage sets `status = failed` with the error retained in logs, not silently
  swallowed.

### 6.4 Retrieval (`rag/retrieval.py`)

`get_relevant_chunks(query, document_id=None, topic=None, top_k=5)`:
- Embeds the query (topic string, or a generation-intent string) via the same
  `EmbeddingProvider`.
- Queries the `VectorStore`, optionally filtered to a specific `document_id` or `topic`.
- Returns chunk texts + chunk ids (the ids are what get recorded in
  `metadata.rag_usage`).

### 6.5 Prompt grounding (`rag/grounding.py`)

Folds retrieved chunk text into the generation prompt with explicit instructions to only
use the provided material and to prefer stating "insufficient information" over
inventing content beyond it — this is what the Groundedness rubric dimension
(§ SYSTEM_DESIGN.md 4.1) checks after the fact. The chunk ids used are attached to the
`LLMResult`'s call site so `metadata/logger.py` can persist `rag_usage` alongside the
rest of the call's metadata in one write.

---

## 7. Evaluation System Implementation

### 7.1 Rubric execution (`services/evaluation.py`, `core/rubric.py`)

- A `Rubric` is loaded by `(type, rubric_id, rubric_version)` — rubrics are versioned
  files/records the same way prompts are (`prompts/judge_mcq_v1.txt` pairs with a rubric
  definition covering the dimensions in § SYSTEM_DESIGN.md 4.1).
- The judge prompt embeds: the question + payload, the rubric's dimension definitions
  (name + scoring guide per level, not just a name), and the reference answer if present.
- The `LLMProvider` is instructed to return a fixed JSON shape:
  `{dimension_key: {score: int, rationale: str}, ...}`.

### 7.2 Scoring pipeline

1. Call `LLMProvider.generate` with the judge prompt.
2. Parse the JSON response; on parse failure, retry once with a corrective follow-up,
   then mark the evaluation attempt as failed (logged via metadata, no `Evaluation` row
   written) rather than fabricating a score.
3. Apply the rubric's threshold rules (defined per rubric, e.g. "Correctness < 3 ->
   fail regardless of other dimensions") to compute `overall_verdict`.
4. Persist the `Evaluation` row (Section 4.2) and update `questions.status`:
   `pending_review` if verdict is `pass`/`needs_review`, `rejected` if `fail`.

### 7.3 Storing results

Evaluations are append-only (Section 4.2) — re-evaluating a question version (new rubric
version, new judge model, part of an Experiment) always inserts a new row. `GET
/evaluations/{question_id}` (Phase 2) or the equivalent repository call in Phase 1 returns
the full history, and "current" evaluation is simply the most recent row unless an
Experiment is explicitly comparing across a set.

---

## 8. SME Review System Implementation

### 8.1 Review APIs / service surface

Phase 1: `services/review.py` exposes `submit_review(question_id, question_version,
reviewer_id, decision, feedback: ReviewFeedback, edited_payload: dict | None)`. Phase 2
wraps this 1:1 as `POST /reviews` (Section 5).

`ReviewFeedback` (Pydantic): `reason_category: ReasonCategory | None`, `comment: str |
None`, `severity: Severity | None`. `reason_category` is required by validation whenever
`decision != "approve"` — enforced in `core/models.py`, not left to UI discipline.

### 8.2 Version control for edited questions

```python
def submit_review(question_id, question_version, reviewer_id, decision, feedback, edited_payload=None):
    original = questions_repo.get(question_id, question_version)
    if decision == "edit":
        new_version = questions_repo.insert_new_version(
            base=original,
            payload=edited_payload,
            created_by=reviewer_id,
            parent_id=original.id,
            parent_version=original.version,
        )
        questions_repo.update_status(question_id, question_version, "edited")
        linked_new_version = new_version.version
    else:
        questions_repo.update_status(
            question_id, question_version,
            "approved" if decision == "approve" else "rejected",
        )
        linked_new_version = None

    reviews_repo.insert(Review(
        question_id=question_id, question_version=question_version,
        reviewer_id=reviewer_id, decision=decision,
        reason_category=feedback.reason_category, comment=feedback.comment,
        severity=feedback.severity, linked_new_version=linked_new_version,
    ))
```

`insert_new_version` is the only place a new row is ever written for an existing lineage
— there is no `UPDATE questions SET payload = ...` anywhere in the codebase. This is
enforced by code review discipline plus a repository-layer test asserting the table's
`(id, version)` pairs are append-only across a review flow.

### 8.3 Linking reviews to questions

Every `Review` row carries the exact `(question_id, question_version)` it acted on
(Section 4.3), and `edit` reviews additionally carry `linked_new_version`. This makes the
full chain in § SYSTEM_DESIGN.md 5.3 (generated version -> evaluations -> review -> new
version -> its own evaluations/review) a straightforward recursive query on
`questions`/`evaluations`/`reviews` keyed by `id`.

### 8.4 Storing reviewer metadata

`reviewer_id` on both `reviews` and, when set via edit, `questions.created_by` is enough
for Phase 1 (single-user or small-team SME pool, no auth system yet). If multi-reviewer
workflows grow, a `reviewers` table (id, name, role) is a additive, non-breaking addition
— nothing else in the schema needs to change since `reviewer_id` is already a foreign-key
shaped column.

### 8.5 Using SME feedback for future improvement

Implementation of § SYSTEM_DESIGN.md 2 and 5.4 as queries, not new infrastructure:
- **Rejection-pattern query**: `GROUP BY reason_category` joined through
  `questions.generation_metadata_id -> metadata_logs.prompt_version`, filtered by topic —
  surfaces which prompt version is producing which failure category, at what rate.
- **Edit-diff analysis**: compare `payload` JSON between a version and its
  `parent_version` for all `edit`-decision reviews — run periodically (or on-demand from a
  Streamlit "insights" view) to surface systematic patterns (e.g. explanations
  consistently getting lengthened by SMEs, signaling the generation prompt under-specifies
  explanation depth).
- **Judge/SME agreement query**: join `evaluations.overall_verdict` against
  `reviews.decision` for the same `(question_id, version)` — a persistent mismatch rate on
  a given dimension is the trigger to revise that rubric's threshold or prompt wording.

None of this needs a separate analytics pipeline at Phase 1 scale — it's SQL over tables
that already exist, surfaced in a Streamlit view.

---

## 9. Provider Abstraction

### 9.1 LLM interface (`llm/base.py`)

```python
class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str

class LLMResult(BaseModel):
    text: str
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    cost_usd: float
    raw_response: dict | None = None   # kept for debugging, never parsed by callers

class LLMProvider(Protocol):
    def generate(
        self,
        messages: list[Message],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        response_format: Literal["text", "json"] = "text",
    ) -> LLMResult: ...
```

`groq_provider.py` implements this by translating `messages`/`model`/params into Groq's
SDK call shape and translating Groq's response (including Groq's own usage fields) back
into `LLMResult`, computing `cost_usd` from a per-model rate table it owns internally. No
other module ever imports the Groq SDK — `services/generation.py` and
`services/evaluation.py` depend only on `LLMProvider`.

**Adding a new provider** (OpenAI, Anthropic, an open-source endpoint) means: implement
`LLMProvider` for it, add it to `llm/registry.py`'s config-driven selection map, add its
pricing table. Zero changes to `services/`, `prompts/`, or anything downstream — this is
the concrete mechanism behind the "provider-agnostic" golden rule in `CLAUDE.md`.

### 9.2 Embedding interface (`embeddings/base.py`)

```python
class EmbeddingResult(BaseModel):
    vectors: list[list[float]]
    model: str
    provider: str
    input_tokens: int
    latency_ms: float
    cost_usd: float

class EmbeddingProvider(Protocol):
    def embed(self, texts: list[str], model: str) -> EmbeddingResult: ...
```

Same swap mechanism as `LLMProvider`: `cohere_provider.py` today, anything else later,
selected by `embeddings/registry.py`.

### 9.3 Vector store interface (`rag/vector_store.py`)

```python
class VectorStore(Protocol):
    def add(self, ids: list[str], vectors: list[list[float]], metadata: list[dict]) -> None: ...
    def query(self, vector: list[float], top_k: int, filter: dict | None = None) -> list[VectorMatch]: ...
```

Backed by chromadb in-process for Phase 1; a hosted vector store implementing the same
Protocol is a Phase 2/3 swap isolated entirely to `rag/`.

### 9.4 Provider selection

`config/settings.py` holds non-secret defaults (`default_llm_model`,
`default_embedding_model`, token caps). Actual provider instances are constructed once
(per Streamlit session, using the visitor's session-held API key — never persisted) via
`llm/registry.py` / `embeddings/registry.py`, which read the configured provider name and
return the matching concrete implementation behind the Protocol type. Feature code never
imports a concrete provider class, only the Protocol.

---

## 10. Tech Stack Suggestions

| Concern | Phase 1 choice | Justification |
|---|---|---|
| UI / entry point | Streamlit, calling services in-process | Fastest path to a working demo for a solo dev; no HTTP layer to maintain until something external actually needs it |
| Backend framework | None (Phase 1) -> FastAPI **[Phase 2]** | FastAPI pairs naturally with the Pydantic models already used throughout `core/`; adding it later is a thin wrapper (Section 5), so paying its complexity cost now buys nothing |
| Database | SQLite -> Postgres **[Phase 2/3, if triggered]** | SQLite needs zero setup/hosting for a solo project and single-writer demo traffic; the repository layer (Section 1.2) is the seam that makes the swap a connection change, not a rewrite — see `docs/DEPLOYMENT.md` for the exact trigger (2+ concurrent writers / always-on) |
| Vector store | chromadb, in-process | No hosting cost or infra for a demo-scale corpus; same Protocol swap story as the DB if corpus size or multi-instance hosting later demands a hosted store |
| RAG "tooling" | Hand-rolled chunking/retrieval, no framework | A full RAG framework's abstractions (chains, retrievers, agents) are overhead for three straightforward steps (chunk, embed, retrieve) and would obscure exactly the mechanics an interviewer wants to hear explained directly; also keeps every provider call routed through the one metadata-logging chokepoint the golden rules require, which a framework's own abstraction layer would fight |
| Evaluation tooling | Hand-rolled rubric runner (Section 7) | Full control over rubric structure, judge-bias mitigations (Section 4 of `SYSTEM_DESIGN.md`), and how results tie into the versioning/review model — the point of this project; LangSmith/RAGAS are built for teams standardizing eval across many projects, which is not this project's problem yet. Revisit only if a Phase 3 need emerges for large-scale automated regression testing across many prompt/model variants simultaneously |
| LLM provider | Groq first, behind `LLMProvider` | Fast + cheap inference, good for a public BYO-key demo where visitors don't want to wait; interface makes OpenAI/Anthropic/open-source additions later a same-shape change |
| Embedding provider | Cohere first, behind `EmbeddingProvider` | Solid general-purpose embeddings with a straightforward API; same swappability story |
| Logging / monitoring | `metadata_logs` table + Streamlit views | At this scale, "monitoring" is "can I query cost/latency/error rate over time," which SQL over an already-required table answers directly; a dedicated observability tool is unjustified overhead until there's production traffic and an on-call rotation to serve |
| Background jobs | None — synchronous calls | Ingestion/generation/evaluation latency is within what a Streamlit spinner can reasonably cover at demo scale; introduce a queue only if uploads/batch generation grow large enough to block the UI unacceptably |

---

## 11. Streamlit UI Design

| Page | Purpose | Key components | Calls |
|---|---|---|---|
| **Generate** | Create a question (topic or document-grounded) | Topic input / document picker, type selector, difficulty slider, RAG toggle, "Generate" button, result card showing question + auto-eval-on-generate option | `services.generation.*`, `services.evaluation.evaluate` |
| **Questions** | Browse/filter the stored set | Filters (topic, type, status), table/card list, click-through to detail (all versions + evaluations + reviews for a lineage) | `db.questions_repo.list`, `.get_history` |
| **Evaluate** | Trigger/inspect evaluations | Question picker, rubric display, "Run evaluation" button, per-dimension score + rationale display, verdict badge | `services.evaluation.evaluate`, `db.evaluations_repo.*` |
| **SME Review** | Approve/reject/edit queue | Queue of `pending_review` questions, decision buttons, structured feedback form (reason category dropdown, comment, severity), inline payload editor for `edit` | `services.review.submit_review` |
| **Documents** *(Slice 6)* | Upload + manage RAG sources | Upload widget, status per document (ingested/chunked/embedded/ready), chunk count, topic/tag editor | `services.ingestion.ingest_document`, `db.documents_repo.*` |
| **Experiments** *(Slice 9)* | Compare variants | Variant config form (models/prompts/RAG on-off), run trigger, results table (quality/cost/latency per variant), "promote as default" action | `services.experiment.*` |

Cross-cutting: a sidebar/session widget for the visitor's own API key entry (session-state
only, per `docs/DEPLOYMENT.md`), and a per-call cost/latency readout surfaced wherever a
provider call just happened, sourced directly from the `LLMResult`/`EmbeddingResult`
returned to the calling service.

---

## 12. Development Phases

### Phase 1 — MVP (matches `docs/ROADMAP.md`)
Domain models + SQLite + repositories + metadata module -> provider layer (Groq) + topic
MCQ generation -> Streamlit generate/list UI -> evaluation engine (LLM-as-judge + rubric
runner) -> SME review + versioning -> demo hardening (BYO-key, cost guard, landing page)
-> optional-but-strong: RAG ingestion, RAG-grounded generation, embedding-based dedup.
Deployed as a public Streamlit Community Cloud demo.

### Phase 2 — Depth
Experimentation system (compare model/prompt/RAG variants with aggregate metrics) ->
FastAPI layer over the existing services (Section 5) for external consumers -> new
question types (True/False, Fill-in-Blank if not already done in Phase 1, then Essay,
Matching, Ordering per § SYSTEM_DESIGN.md 8) -> Postgres migration only if a concurrency
trigger actually fires.

### Phase 3 — Scale (build only if a real trigger fires, per `docs/DEPLOYMENT.md`)
Hosted vector store (large corpus / multi-instance hosting) -> background job queue for
ingestion/batch generation -> multi-reviewer workflows with a real `reviewers`/auth table
-> revisit evaluation tooling (LangSmith/RAGAS or similar) only if standardizing eval
across a much larger prompt/model surface becomes the actual bottleneck -> monitoring
dashboards beyond SQL-over-`metadata_logs` if there's real production traffic to watch.

---

## 13. Tradeoffs

### 13.1 Cost vs. performance
- **BYO-key model** shifts inference cost to visitors entirely, which removes the usual
  cost-vs-quality tension for the owner — but it does mean the app must default to a cheap,
  fast model and cap tokens (`docs/DEPLOYMENT.md`) so a stranger's key isn't drained by a
  runaway loop or an overly large `top_k`/context.
- **Groq's speed** is a UX win for a synchronous, spinner-driven demo (no background jobs
  needed at Phase 1), but ties the default-model choice to whatever Groq hosts — a
  provider swap for higher-quality-but-slower output is a config change, not a rewrite,
  by design (Section 9.1).
- **Rubric-based judging** costs one extra LLM call per question compared to no
  evaluation at all; this is accepted because the two-gate filtering model
  (§ SYSTEM_DESIGN.md 2) is the core value proposition of the product, not an optional
  add-on.

### 13.2 Managed vs. open-source / self-hosted
- **SQLite over managed Postgres**: zero hosting cost/setup for a solo demo; the tradeoff
  is no real concurrent-write support, which is fine until it isn't — the repository-layer
  seam (Section 1.2) exists specifically so that migration is cheap when the trigger fires,
  rather than paying Postgres's operational overhead from day one for traffic that doesn't
  need it.
- **In-process chromadb over a hosted vector DB**: same logic — no infra to manage, no
  network latency for retrieval, at the cost of not scaling past what fits comfortably in
  one process's memory/disk. Acceptable for a demo-scale document corpus.
- **Hand-rolled RAG/eval over frameworks (LangChain-style, LangSmith/RAGAS)**: more code
  to write, but full transparency into every prompt, every score, every provider call —
  which is both an interview-defensibility requirement (`docs/BUILD_GUIDE.md`) and a
  genuine architectural benefit (nothing hidden behind a framework abstraction fights the
  "log every call" golden rule).

### 13.3 Scaling decisions
- Every scaling lever is deliberately deferred behind an interface rather than
  pre-built: DB (repository layer), vector store (`VectorStore` Protocol), API surface
  (`services/` boundary), LLM/embedding provider (Protocols). This means scaling decisions
  get made **when a real trigger fires** (traffic, corpus size, external consumers,
  concurrency), each isolated to one layer, instead of being guessed at upfront and
  over-built for a solo-dev demo that may never need them — directly following the
  "avoid overengineering early" constraint this document was scoped under.
- The one place scale is *not* deferred is metadata logging (Section 3.4) — it's cheap to
  do from day one and is the prerequisite data for every later scaling *decision*
  (knowing cost/latency/volume trends is what tells you a trigger has actually fired,
  rather than guessing).
