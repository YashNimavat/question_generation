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
  an SME edit is itself signal for the improvement loop (`SYSTEM_DESIGN.md` §1.7, §2) — the
  pre-edit version shows exactly what the LLM got wrong. Overwriting it in place would
  destroy that diff, break the audit trail of who changed what and when, and leave
  `Evaluation`/`Review` rows pointing at a version that silently changed underneath them.
  `questions_repo.insert_new_version` is the only path that writes a new `(id, version)`
  row for an existing lineage (Slice 5); there is no `UPDATE questions SET payload = ...`
  anywhere in the codebase.
- Embedding-based deduplication over exact-match -> why: LLM-generated near-duplicates are
  almost never character-for-character identical (reworded stems, swapped distractor order,
  synonym substitution), so an exact-match check would miss the overwhelming majority of
  real duplication. Comparing stem embeddings by cosine distance catches semantic
  restatement, not just literal repetition, at the cost of needing a tunable similarity
  threshold rather than a binary match (Slice 8).
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

## Slice 5

- **`evaluate()` now sets `pending_review` instead of `auto_evaluated` on a pass/
  needs_review verdict**: this was a pre-existing gap against `SYSTEM_DESIGN.md` §1.6's
  lifecycle (`auto_evaluated -> pending_review -> approved/rejected/edited`) — nothing
  previously wrote `pending_review`, so the review queue would have had no well-defined
  status to query. Fixing the one-line branch in `services/evaluation.py` (Slice 4 code)
  was in scope for Slice 5 because the review queue's correctness depends on it directly.

- **`reviewer_id` as a free-text session input, no `reviewers` table**: matches
  `docs/TECH_ARCHITECTURE.md` §8.4 — Phase 1 has no auth system and a single/small SME
  pool, so a plain text box (same pattern as the BYO-API-key input on other pages) is
  enough. `reviewer_id` is already a foreign-key-shaped column, so a real `reviewers`
  table is a strictly additive change later, not a migration.

- **Edit form built for `McqPayload` only**: `generate_mcq` is still the only generator
  implemented (`services/generation.py`) — True/False and Fill-in-Blank payload models
  exist but nothing produces them yet, so an editor for those types would have no
  question to ever act on. `services/review.py`'s `submit_review` itself is fully
  type-agnostic (`type(original.payload)(**edited_payload)`); only the Streamlit inline
  editor is MCQ-specific, and adding a T/F or Fill-in-Blank editor later is an additive
  UI change, not a service-layer one.

- **`submit_review` validates before mutating**: the reason-category-required-unless-
  approve check runs before any repository write. Early drafts constructed the `Review`
  Pydantic model (which owns that validation) only after calling `update_status` /
  `insert_new_version` — a rejected review with no reason would have already changed the
  question's status with no `Review` row to show for it. The check was hoisted above all
  mutations so a validation failure is always a no-op against the DB.

## Slice 6

- **`pypdf` + `python-docx` over `unstructured`**: two small, format-specific libraries
  are enough to extract raw text for chunking (`docs/TECH_ARCHITECTURE.md` SS6.1 only
  calls for "accept an uploaded file, extract raw text" — no layout/table-aware parsing
  is needed yet). `unstructured` pulls in a much larger dependency tree for capabilities
  this slice doesn't use, which conflicts with "no premature abstraction... keep it
  simple for a solo dev."

- **Word-count chunk-size approximation over a real tokenizer**: `rag/chunking.py`
  approximates `docs/TECH_ARCHITECTURE.md` SS6.2's "~500 tokens" default as 375 words
  (~0.75 tokens/word) rather than adding `tiktoken` or a model-specific tokenizer. The
  project has no OpenAI dependency to tie a tokenizer to, and an approximate chunk size
  is good enough for a demo-scale corpus — precise token accounting matters for LLM/
  embedding cost logging (which uses each provider's real usage numbers), not for
  deciding where a chunk boundary falls.

- **Original uploaded file discarded after text extraction, never written to disk**:
  `services/ingestion.py` extracts text from the uploaded bytes in memory and never
  persists the original PDF/DOC. `docs/TECH_ARCHITECTURE.md` SS6.1's ingestion flow never
  mentions storing the source file, and skipping it avoids a new file-storage concern
  (retention, disk growth, `.gitignore` surface) for a slice scoped to ingestion only.

- **`EmbeddingProvider.embed()` hardcodes `input_type="search_document"`**: Cohere's v3
  embed models require an `input_type` to distinguish documents being indexed from
  queries being searched, but Slice 6 is ingestion-only — every call embeds source
  chunks, never a query. The `EmbeddingProvider` Protocol itself stays exactly as
  `docs/TECH_ARCHITECTURE.md` SS9.2 specifies it (`embed(texts, model)`, no extra
  parameter); Slice 7 (RAG-grounded generation) is where query-side embedding is
  introduced, and that's the right place to revisit whether `input_type` needs to
  surface through the interface.

- **Chunk overlap is best-effort, not a strict guarantee**: `rag/chunking.py` packs
  whole paragraphs into a chunk and only carries a paragraph into the next chunk's
  overlap if it independently fits within the overlap-word budget; a single paragraph
  larger than that budget produces zero overlap at that boundary rather than splitting
  it. A paragraph that exceeds the chunk-size budget on its own is hard-sliced into
  fixed-stride word windows instead, which does guarantee overlap within it. This keeps
  the algorithm simple and always terminating (no risk of an oversized chunk or an
  infinite carry-over loop) at the cost of not hitting the ~15% overlap target exactly
  at every boundary — acceptable given chunking is already a word-count approximation.

## Slice 7

- **`EmbeddingProvider.embed()` gains `input_type: str = "search_document"`**: resolves
  the open question left by Slice 6. The default preserves every existing call site
  (ingestion never passes it), and `rag/retrieval.py` is the one new caller that passes
  `input_type="search_query"` explicitly. An `embed_query()` sibling method was
  considered but rejected — one method with an explicit parameter is a smaller Protocol
  surface than two methods that would otherwise share their entire batching/pricing
  implementation.

- **Retrieval scope is document-picker-only, no topic-wide cross-document search**:
  `rag/retrieval.py::get_relevant_chunks` requires a `document_id` and filters
  `VectorStore.query()` by it. `docs/TECH_ARCHITECTURE.md` SS6.4 leaves room for
  topic-only retrieval across all documents, but that needs ranking/aggregation logic
  this slice doesn't need — the UI already has a per-document picker from Slice 6, so
  requiring a selection keeps `get_relevant_chunks` a thin, fully-tested wrapper around
  the existing `VectorStore.query(filter=...)` primitive. Topic-wide retrieval is
  deferred until a concrete need for it shows up.

- **New `prompts/mcq_grounded_v1.txt` instead of branching `mcq_v1.txt`**: keeps the
  topic-only generation path (prompt text, `PROMPT_VERSION`, and its tests) completely
  untouched by this slice. `services/generation.py::generate_mcq` picks the prompt file
  and version based on whether `document_id` is set, matching the "prompts are versioned
  files, reference by version string" convention rather than growing one template two
  behaviors.

- **`rag_usage` stays an untyped `dict[str, Any]`**: `metadata/models.py::MetadataRecord
  .rag_usage` was already this shape from Slice 2 groundwork and every other metadata
  field on that model is similarly loose. `generate_mcq` builds
  `{"document_id": ..., "chunk_ids": [...]}` inline at the call site per
  `docs/TECH_ARCHITECTURE.md` SS4.6 rather than introducing a `RagUsage` Pydantic model
  the docs don't call for.

- **Zero retrieved chunks raises `GenerationError`, no silent fallback to topic-only
  generation**: if `document_id` is set but `get_relevant_chunks` returns nothing (e.g.
  the document has no chunks close to the topic), `generate_mcq` fails loudly instead of
  quietly generating an ungrounded question under a `source=Source.DOCUMENT` label — that
  would defeat the traceability `rag_usage` exists for.

- **Groundedness rubric dimension deferred**: `docs/SYSTEM_DESIGN.md` SS4.1 calls out a
  document-generation-specific "Groundedness" rubric dimension as the natural consumer of
  `rag_usage` on the evaluation side. `core/rubric.py` still only has `MCQ_RUBRIC_V1`'s
  five non-RAG dimensions — out of scope for this slice, which is generation-only, and
  left for whichever slice next touches `core/rubric.py` or the evaluation engine.

- **(Review pass) `rag/retrieval.py::get_relevant_chunks` now logs its query-side embed
  call via `log_call(operation_type=OperationType.EMBEDDING, ...)`**: the first draft
  called `embedding_provider.embed()` without logging it, unlike the identical
  document-side call in `services/ingestion.py`, silently violating CLAUDE.md's "every
  LLM/embedding operation logs metadata... no silent calls" rule — every grounded
  generation attempt (including ones that go on to fail with zero retrieved chunks) was
  a real, billed Cohere call with no `metadata_logs` row. Fixed by threading `db_path`
  through `get_relevant_chunks` and logging immediately after the embed call, same as
  ingestion does.

- **(Review pass) `generate_mcq` wraps `get_relevant_chunks`'s `ValueError`
  (no `cohere_api_key` configured) into `GenerationError`**: the first draft let this
  propagate raw, so a user with a Groq key but no Cohere key would hit an unhandled
  exception/traceback on the Generate page instead of a friendly `st.error` message —
  the RAG toggle intentionally makes Cohere optional until it's actually used. Fixed the
  same way `services/ingestion.py` already wraps this exact `ValueError` into
  `IngestionError`, so both RAG entry points fail the same way.

## Slice 8

- **Dual-threshold duplicate policy, not a single cutoff**: a hard threshold
  (`dedup_hard_threshold`, cosine distance <= 0.05) auto-rejects near-exact rewordings
  the same way the auto-eval gate auto-rejects clearly-bad questions; a softer threshold
  (`dedup_soft_threshold`, <= 0.15) instead flags the question (persisted normally,
  `duplicate_of_id`/`duplicate_of_version`/`duplicate_score` set) so the SME sees
  "similar to existing question X" during review and makes the judgment call, per
  `SYSTEM_DESIGN.md`'s "either auto-discarded or surfaced to the SME... a policy choice"
  framing. Both thresholds are `config/settings.py` fields, not constants buried in
  `services/dedup.py`, so they're tunable in the same place as every other default
  (`default_llm_model`, `chroma_persist_dir`, etc.) rather than requiring a code change.

- **Comparison pool resolved live against SQLite, not by filtering Chroma metadata**:
  the new `questions` Chroma collection is queried filtered only by `topic`; for each
  candidate match, `services/dedup.py::check_similarity` looks up the question's
  *current* status via `questions_repo.get()` and discards anything not
  `approved`/`pending_review`. This avoids having to keep Chroma metadata in sync every
  time a question's status changes elsewhere (evaluation, review) — status stays
  single-sourced in SQLite, Chroma only ever stores the vector + a stable identity.

- **Separate `questions` Chroma collection (cosine space) from the existing `chunks`
  collection**: question-stem embeddings and document-chunk embeddings are different
  vector spaces: comparing across them would be meaningless, and `chunks` isn't
  configured for cosine distance (its distance metric was never load-bearing for RAG
  retrieval ranking, only for dedup's threshold semantics). `ChromaVectorStore` gained
  optional `collection_name`/`metadata` constructor params so both collections share one
  implementation without changing default (RAG) behavior.

- **One embedding call per generation, reused for both the similarity check and
  indexing**: `check_similarity` and `record_question_embedding` both take an
  already-computed vector rather than each embedding independently — `generate_mcq`
  embeds the stem exactly once via `dedup.embed_stem`. Embedding twice per generation
  would double dedup's Cohere cost/latency for no benefit.

- **Missing/invalid embedding key skips dedup gracefully instead of failing
  generation**: unlike the RAG-grounded path (which *requires* Cohere and wraps a
  missing-key `ValueError` into a hard `GenerationError`), topic-only generation has
  never needed an embedding key before this slice. Making dedup mandatory would mean a
  BYO-key visitor with only a Groq key could no longer generate any question at all —
  a much bigger regression than just not getting duplicate-checked. `dedup.embed_stem`
  catches the missing-key `ValueError` and returns `None`; `generate_mcq` treats that as
  "dedup unavailable for this call" and persists the question normally with no
  duplicate fields set, rather than raising. The tradeoff: without a Cohere key, the
  dataset can silently accumulate duplicates for that visitor's session — accepted
  because generation working at all is a stronger requirement than generation being
  duplicate-checked, and this only affects visitors who never configured embeddings in
  the first place (anyone using RAG already needs the key, so this mainly affects
  topic-only, no-RAG usage).

- **Rejected duplicates are persisted, not silently dropped**: a hard-rejected
  duplicate is still written to `questions` with `status=rejected` and
  `duplicate_of_id`/`duplicate_score` set (same shape the auto-eval-fail path already
  uses), matching `SYSTEM_DESIGN.md`'s "Storage: all versions, all decisions, retained"
  principle — it's real signal for rejection-pattern analysis (how often does a given
  topic/prompt version generate near-duplicates), not just noise to discard. It is,
  however, *not* re-indexed into the `questions` Chroma collection itself (only
  non-hard-rejected questions are), since a rejected duplicate shouldn't itself become a
  future comparison target.

## Slice 9

- **`prompt_version` added as a real `generate_mcq` axis, `mcq_v2.txt` written as a
  genuinely different prompt (not a throwaway file)**: prior to this slice, the only
  overridable generation axes were `model` and `document_id` (RAG on/off) —
  `SYSTEM_DESIGN.md` §7.1 also calls for comparing prompt versions, so `mcq_v2.txt`
  additionally requires the `explanation` field to state why the strongest distractor
  is wrong (implementing `SYSTEM_DESIGN.md` §3.1's MCQ explanation guidance, which
  `mcq_v1.txt` never did), giving prompt-version a real, testable difference. The
  override only applies to topic-only generation; combining it with `document_id`
  raises `GenerationError`, since the grounded pipeline has one prompt.

- **Single-axis-per-experiment enforced in `services/experiment.py`, not left as UI
  guidance**: `_validate_variants` raises if more than one of `{model, prompt_version,
  document_id}` takes more than one distinct value across a variant set, per
  `SYSTEM_DESIGN.md` §7.1 ("comparing model A/prompt-v1 against model B/prompt-v2
  conflates two variables"). The Streamlit page also picks a single axis via a radio
  button, so an experiment is single-variable by construction on both sides, not just
  documented as a convention.

- **`run_experiment` skips a failed sample and continues, rather than aborting the
  whole comparison**: a `GenerationError`/`EvaluationError` on one sample out of
  `sample_size` would otherwise throw away every other already-generated sample in the
  run. The resulting lower `run_count` for that variant is itself surfaced in
  `aggregate_results` as a visible signal (a variant that fails often *should* look
  worse), not something to paper over.

- **Diversity metric redesigned during planning to avoid conflating three different
  populations**: the original plan reused the existing `duplicate_of_id`/
  `duplicate_score` fields (set by Slice 8's dedup gate at generation time) as an
  experiment "diversity" metric. That would have been wrong: `check_similarity` checks
  against the persisted, topic-scoped Chroma `questions` collection, and
  `generate_mcq` indexes each new question into that same collection immediately after
  persisting it — so within one `run_experiment` loop, earlier samples leak into later
  samples' dedup checks, and (since topic is held constant across variants in one
  experiment by design) *a different variant's* samples would leak in too, making a
  variant look artificially less diverse for reasons having nothing to do with its own
  output. Fix: `services/dedup.py::batch_near_duplicate_rate` computes diversity
  independently at `aggregate_results` time, via a fresh batch embedding call scoped
  strictly to one variant's own stems from this experiment — no `vector_store`/topic
  param at all, so it structurally cannot see the persisted pool or another variant's
  batch. `duplicate_of_id` keeps doing its original Slice 8 job (keeping the stored
  dataset clean) unchanged; the two mechanisms are now fully independent. Reuses
  `settings.dedup_soft_threshold` for the "near-duplicate" cutoff rather than adding a
  new tunable, since it's the same semantic meaning Slice 8 already established.

- **Auto-eval-vs-SME "agreement" metric (`SYSTEM_DESIGN.md` §7.2) deferred**: this
  synchronous, single-run `run_experiment` flow produces Questions and Evaluations but
  no SME Review records, so there's nothing to measure agreement against yet. Left for
  whichever slice next builds a review queue that specifically targets
  experiment-generated questions.

- **`VariantMetrics` is a local, non-persisted Pydantic model in
  `services/experiment.py`** (same pattern as `services/dedup.py`'s `DedupResult`):
  aggregation is a read-time computation over existing `Question`/`Evaluation`/
  `MetadataRecord` rows via existing repository functions, per
  `TECH_ARCHITECTURE.md` §3.5 — no new raw SQL, no new results table.