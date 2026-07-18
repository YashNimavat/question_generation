# Question Intelligence System — Final Build Guide

A portfolio-grade, industry-standard build of a GenAI system: generate questions with
LLMs, evaluate them with LLM-as-judge, add SME (human) review, and improve a question
dataset over time. Built as a personal, clean-room reimplementation of a system concept
(no company code, prompts, data, or secrets reused).

Save this file as `docs/BUILD_GUIDE.md` in your project. Work through it in Claude Code,
one vertical slice at a time.

---

## 0. What this guide optimizes for

Two goals at once, and they don't conflict:
- **Learning by implementing** — you write the GenAI-core logic yourself so you can
  defend every choice in an interview.
- **Industry standard** — provider abstraction, metadata/cost tracking, tests, clean
  layering, a real README, a live demo. Nothing toy-grade.

### Interview framing (say it exactly like this)
> "I built a system like this at a previous company. This repo is my own clean-room
> reimplementation — my code, my design decisions — built to demonstrate the approach.
> No proprietary code, prompts, or data are reused."

That is honest, holds up under questioning, and protects you legally. The public repo,
the design docs, and the decisions log are your thinking on display — the whole point.

---

## 1. How the build works (read first)

You build in **vertical slices**: each slice runs end-to-end, is tested, and is committed
before the next begins.

### The "who drives" rule — this is the key to the learning goal
- **YOU DRIVE** the GenAI-core slices (provider abstraction, LLM-as-judge, RAG grounding,
  SME/versioning). Write the first draft yourself; Claude reviews, hardens, and tests.
  These are exactly what an interviewer drills into.
- **CLAUDE DRIVES** the plumbing (repository layer, Streamlit pages, boilerplate). You
  review to understand it, but there's less to be asked about.
- Simple test: *the more likely an interviewer asks about it, the more of it you write.*

### The three rules that keep it on track
1. **One slice per plan-mode session, fresh context each time.** Broad plans are shallow;
   narrow plans are sharp.
2. **Always load `CLAUDE.md` + `docs/` at the top of every prompt, and always demand
   tests.** Keeps the provider-agnostic and metadata rules from eroding.
3. **Defer explicitly** ("no RAG", "no UI", "Slice X only"). Unscoped, Claude builds
   ahead and tangles slices.

### The per-slice loop
1. `Shift+Tab` to enter plan mode.
2. Paste the slice prompt.
3. Answer Claude's clarifying questions.
4. Read the plan, push back / refine, then approve.
5. Execute; run `uv run pytest`.
6. **Do the "Interview prep" checklist for that slice (below) — write your own notes.**
7. Commit. Fresh session for the next slice.

---

## 2. Setup files — create before building

Six files. Four are drafted in full here; two you generate by running your own design
prompts.

### `CLAUDE.md` (project root — read automatically every session)

```markdown
# Question Intelligence System

A GenAI product for generating, evaluating, and improving high-quality question datasets
using LLMs, with SME (human) review in the loop.

## Reference docs — read before planning any feature
- `docs/SYSTEM_DESIGN.md`     — product/system design (entities, lifecycle, review model)
- `docs/TECH_ARCHITECTURE.md` — technical architecture reference
- `docs/TECH_DECISIONS.md`    — locked stack, structure, conventions
- `docs/DECISIONS.md`         — why-X-over-Y log (interview material)
- `docs/ROADMAP.md`           — phases and what is deferred
- `docs/DEPLOYMENT.md`        — when and how to go online

## Golden rules
- Provider-agnostic. NEVER call Groq/Cohere SDKs directly in feature code. Always go
  through the `llm/` and `embeddings/` interfaces.
- MVP entry point is Streamlit calling internal service functions directly. Do NOT add
  FastAPI/HTTP until Phase 2.
- Build one vertical slice at a time. Don't scaffold features outside the current slice.
  When in doubt, ask before expanding scope.
- Every LLM/embedding operation logs metadata (model, prompt_version, tokens, latency,
  cost, rag_usage) via the metadata module. No silent calls.
- Secrets NEVER in the repo. Read provider keys from config/secrets only.
- Keep it simple for a solo dev; no premature abstraction beyond the provider layer.

## Conventions
- Python 3.11+, package manager `uv`.
- Data models: Pydantic. DB access via a repository layer, never raw SQL in the UI.
- Prompts live in `prompts/` as versioned files; reference by version string.
- A test for every service function and every LLM-judge before moving on.
- Update the relevant `docs/` file whenever architecture changes.

## Commands
- Install: `uv sync`
- Run app: `uv run streamlit run app/main.py`
- Test: `uv run pytest`
```

### `docs/TECH_DECISIONS.md`

```markdown
# Tech Decisions (locked for MVP)

## Stack
- Python 3.11+, `uv`
- UI: Streamlit (MVP is UI -> services directly, no HTTP layer)
- LLM: Groq first, behind a provider-agnostic `LLMProvider` interface
- Embeddings: Cohere first, behind a swappable `EmbeddingProvider` interface
- Database: SQLite for MVP; repository layer written so Postgres is a drop-in later
- Vector store: local (chromadb in-process), behind a `VectorStore` interface

## Secrets & cost (public demo)
- Visitors bring their OWN API keys (pasted into the UI, held in session only, never
  stored, never logged). Zero cost to the owner.
- No key is ever written to disk or committed. Owner's own keys, if any, live only in
  Streamlit secrets for local/testing.

## Deferred (NOT in MVP)
- FastAPI / REST API           -> Phase 2 (only when other apps consume the services)
- Postgres / hosted DB         -> when concurrency demands it
- Hosted vector store          -> when corpus is large or app is hosted
- LangSmith / RAGAS            -> evaluate later; MVP uses our own rubric runner
- Essay / Matching / Ordering  -> model must ALLOW these; don't build them yet

## Structure (target)
app/            # Streamlit pages + entry point
core/           # domain models (Pydantic), enums, status
services/       # generation, evaluation, review, experiment, ingestion — UI calls these
llm/            # LLMProvider interface + groq_provider.py
embeddings/     # EmbeddingProvider interface + cohere_provider.py
rag/            # ingestion, chunking, retrieval, vector store interface
metadata/       # metadata logging for every operation
db/             # repositories, schema/migrations
prompts/        # versioned prompt templates
tests/
docs/

## Provider interface rules
- LLMProvider: `.generate(messages, model, ...) -> LLMResult` carrying text + usage
  (tokens, latency, cost). Cost computed per-provider.
- EmbeddingProvider: `.embed(texts, model) -> vectors + usage`.
- VectorStore: `.add(...)`, `.query(...)`.
- Provider selection is config-driven; feature code receives an interface, never a
  concrete provider.
```

### `docs/DECISIONS.md` (your interview cheat sheet — fill as you build)

```markdown
# Design Decisions (why X over Y)

Add an entry as you make each decision. Keep each to 3-5 sentences: the choice, the
alternative, and the reason. This is the highest-signal doc for interviewers.

- Provider abstraction over hardcoding a vendor -> why:
- LLM-as-judge over human-only evaluation -> why:
- Rubric scoring over a raw 1-10 score -> why:
- Reference answers included in evaluation -> why:
- SQLite for MVP over Postgres -> why:
- Streamlit-only MVP over Streamlit+FastAPI -> why:
- Type-discriminated Question model over separate tables per type -> why:
- Versioning edited questions (new version linked to original) over in-place edits -> why:
- Embedding-based deduplication over exact-match -> why:
- Visitor-supplied API keys over owner-funded demo -> why:
```

### `docs/ROADMAP.md`

```markdown
# Roadmap

## Phase 1 — MVP (local, then live via Streamlit Cloud)
Slice 1  Domain models + SQLite schema + repository layer + metadata module
Slice 2  Provider layer (LLMProvider/Groq) + topic-based MCQ generation service
Slice 3  Streamlit UI: generate MCQ + list stored questions
Slice 4  Evaluation engine (LLM-as-judge + rubric runner)
Slice 5  SME review page (approve/reject/edit + versioning)
Slice D  Demo hardening (BYO-key handling, cost guard, landing state)
Slice 6  RAG ingestion (upload -> chunk -> embed -> vector store)   [optional-but-strong]
Slice 7  RAG-grounded generation                                    [optional-but-strong]
Slice 8  Deduplication via embeddings                               [optional]

## Phase 2 — Depth
Slice 9   Experimentation (compare model / prompt / RAG-vs-not)
Slice 10  FastAPI over the same services (for external clients)
Slice 11  New question types (True/False, Fill-in-Blank, then Essay/Matching/Ordering)

## Deferred always-until-needed
Postgres, hosted vector store, monitoring dashboards, LangSmith/RAGAS, multi-tenant.
```

### `docs/DEPLOYMENT.md`

```markdown
# Deployment

## Target: live demo on Streamlit Community Cloud (free, public GitHub repo)

## Pre-deploy checklist (Slice D must be done first)
- Visitor API keys entered in-UI, held in session state only, never stored/logged.
- No secret in the repo or in git history. `.env` gitignored. Own keys only in
  Streamlit secrets for local runs.
- Cost guard: since visitors use their own keys, cap tokens and default to a cheap model
  so a stranger's key isn't drained by accident; show clear usage/cost per call.
- Landing state: a stranger understands the app in ~15 seconds (short intro + a key
  input + a "generate a sample" button).
- README has the demo link + 2-3 screenshots.

## Later scaling (only if a trigger fires — none needed for the demo)
- Two+ concurrent writers / always-on -> SQLite -> Postgres (touches only db/).
- Large corpus / server-side vectors -> hosted vector store (touches only rag/).
- Other apps need an API -> add FastAPI (Slice 10) over the same services.
Each is isolated behind an interface, not a rewrite — that is why we built it this way.
```

### The two generated docs
Run your **product-design prompt** ending with: *"Write this to `docs/SYSTEM_DESIGN.md`."*
Run your **technical prompt** ending with: *"Reference design only — write to
`docs/TECH_ARCHITECTURE.md`. Respect `docs/TECH_DECISIONS.md`: Streamlit-only MVP,
SQLite + local vector store, no LangSmith/RAGAS in Phase 1."*

---

## 3. Step-by-step build

### Step 1 — Generate the two design docs (normal chat, NOT plan mode)
As above. Then save all setup files. **Public GitHub repo from the start** so the design
docs are visible.

### Step 2 — Initialize (normal chat)
> "Run `uv init` with Python 3.11. Create the folder structure from
> `docs/TECH_DECISIONS.md` with empty `__init__.py` and placeholder files. Add a
> `.gitignore` covering `.env`, secrets, `__pycache__`, and the SQLite db file. No logic
> yet."

Verify the tree and `.gitignore` before continuing.

### Step 3 — Build the slices

Each slice below has: **Driver**, the **plan-mode prompt**, and an **Interview prep**
block. After the slice runs, do the prep block and record answers in `docs/DECISIONS.md`
or your own notes. The prep blocks are where an interviewer will push — treat them as the
real deliverable.

---

#### Slice 1 — Domain models + persistence  ·  Driver: CLAUDE (you review)
> "Read CLAUDE.md and all files in docs/. Plan Slice 1 only: Pydantic domain models —
> Question as a type-discriminated model (MCQ/TrueFalse/FillBlank) so new types slot in
> later, plus Evaluation, Review, Document, Experiment — with status and versioning
> fields; the SQLite schema and repository layer; and the metadata logging module. No LLM
> calls, no UI. pytest tests. Ask clarifying questions first, then present ordered steps."

**Interview prep — be able to explain:**
- Why a type-discriminated model instead of a table per question type. What breaks when
  you add Essay later, and why your design avoids it.
- How versioning works: an edited question is a new version linked to the original, not
  an in-place overwrite. Why that matters for dataset quality and auditability.
- What the status field represents across the lifecycle (generated -> evaluated ->
  reviewed -> approved/rejected).

---

#### Slice 2 — Provider abstraction + generation  ·  Driver: YOU (Claude reviews) [CORE]
Write the `LLMProvider` interface and the Groq implementation yourself first. This is
core GenAI engineering.
> "Read CLAUDE.md and docs/. I have drafted `llm/` (interface + groq_provider) and a
> generation service. Review and harden it: confirm the interface is truly
> provider-agnostic, that usage (tokens, latency, cost) is captured and logged via the
> metadata module, and that the generation service persists an MCQ via the repository.
> Add one versioned prompt in prompts/. Add pytest tests with a mocked provider. Point
> out anything not industry-standard. Plan the changes, then apply on approval."

**Interview prep — be able to explain (HIGH-PRIORITY):**
- How the abstraction lets you swap Groq -> OpenAI -> Anthropic without touching feature
  code. Walk through exactly what a new provider must implement.
- How you compute cost per call and why cost/latency tracking matters in production
  GenAI.
- Why prompts are versioned and referenced by version string.

---

#### Slice 3 — Streamlit UI (generate + list)  ·  Driver: CLAUDE (you review)
> "Read CLAUDE.md and docs/. Plan Slice 3 only: a Streamlit page that calls the generation
> service to create a topic-based MCQ and displays it, plus a page listing stored
> questions. UI calls services directly, no HTTP. Ask questions, then present steps."

**Interview prep:** be able to say why the UI calls services directly (no HTTP) for the
MVP, and when you'd introduce an API instead.

---

#### Slice 4 — Evaluation: LLM-as-judge + rubrics  ·  Driver: YOU (Claude reviews) [MOST IMPORTANT]
The single most important slice for a GenAI role. Draft the judge and rubric runner
yourself.
> "Read CLAUDE.md and docs/. I have drafted the evaluation engine: an LLMProvider-based
> judge and a rubric runner that scores a question/answer against a rubric and a reference
> answer, persists an Evaluation, and logs metadata. Review and harden it to
> industry-standard: check for judge robustness (structured/parseable output, guard
> against position/verbosity bias), sensible rubric schema, and correct metadata. Add a
> Streamlit view to trigger and show results. pytest tests with a mocked judge. Plan,
> then apply on approval."

**Interview prep — be able to explain (HIGHEST-PRIORITY):**
- What LLM-as-judge is, and its known failure modes (position bias, verbosity bias,
  self-preference, miscalibration). How your design mitigates them.
- Why rubric-based scoring beats a raw 1-10 number. What your rubric dimensions are.
- Why reference answers improve judge reliability.
- How you'd validate the judge itself (e.g. agreement with human/SME labels) — this is a
  senior-level answer; have it ready even if you don't fully build it.

---

#### Slice 5 — SME review + versioning  ·  Driver: YOU (Claude reviews) [CORE]
Human-in-the-loop and dataset quality — separates product-minded ML engineers from the
rest.
> "Read CLAUDE.md and docs/. I have drafted the SME review system: a Streamlit dashboard
> to approve/reject/edit a question with structured feedback, where an edit creates a new
> version linked to the original and stores reviewer metadata. Review and harden it,
> confirm versioning is correct and auditable, add the service/repository tests. No RAG.
> Plan, then apply on approval."

**Interview prep — be able to explain:**
- How SME decisions feed back into system quality over time (building a high-quality,
  human-verified dataset; identifying prompt/model weaknesses from rejection patterns).
- Why edits are versioned rather than overwritten (auditability, training-data lineage).
- How review + auto-evaluation complement each other (cheap auto filter, expensive human
  judgment where it counts).

---

#### Slice D — Demo hardening  ·  Driver: shared (do BEFORE deploying)
> "Read CLAUDE.md and docs/DEPLOYMENT.md. Plan Slice D only: make the app safe for a
> public demo where VISITORS supply their own Groq/Cohere API keys. Requirements: keys
> entered in the UI, kept in session state only, never written to disk or logs; a token
> cap and a cheap default model so a visitor's key can't be drained accidentally; per-call
> usage/cost shown in the UI; a clear landing state so a first-time visitor understands
> and can generate a sample in ~15 seconds. Verify no secret is committed and `.env` is
> gitignored. Plan, then apply on approval."

**Interview prep — be able to explain:**
- How you handle secrets for a public app and why BYO-key is safe (no key stored, session
  only).
- What cost controls you put in and why they matter for any public GenAI endpoint.

---

#### Step 4 — Deploy
> "Read docs/DEPLOYMENT.md. Walk me through deploying this to Streamlit Community Cloud
> from my public GitHub repo, confirm the pre-deploy checklist is satisfied, and tell me
> exactly what to click."

Get the link. Add it + 2-3 screenshots to the README.

---

#### Optional strong additions (do if time allows; otherwise roadmap them)

**Slice 6 — RAG ingestion · Driver: YOU (Claude reviews) [strong]**
> "Read CLAUDE.md and docs/. I have drafted RAG ingestion: upload a PDF/DOC, chunk it,
> embed via the EmbeddingProvider behind the interface, store vectors via the VectorStore
> interface, persist Document metadata. Review and harden (chunking strategy, interface
> cleanliness), add a Streamlit upload page and tests with a mocked embedder. Plan, then
> apply on approval."
> **Prep:** chunking strategy and tradeoffs; why the embedder/vector store sit behind
> interfaces; how you'd evaluate retrieval quality.

**Slice 7 — RAG-grounded generation · Driver: YOU (Claude reviews) [strong]**
> "Read CLAUDE.md and docs/. Plan Slice 7 only: retrieve relevant chunks for a topic/doc,
> ground the generation prompt, and log rag_usage (doc_id, chunks) in metadata. Add a RAG
> toggle to the generation UI. Tests. Ask questions, then present steps."
> **Prep:** how grounding reduces hallucination; why you log which chunks were used
> (traceability); RAG vs non-RAG tradeoffs.

**Slice 8 — Deduplication · Driver: CLAUDE (you review)**
> "Read CLAUDE.md and docs/. Plan Slice 8 only: embed new questions and flag/reject
> near-duplicates against stored ones using the VectorStore, wired into generation.
> Tests. Ask questions, then present steps."
> **Prep:** why embedding-similarity dedup over exact match; how you pick a threshold.

---

#### Phase 2 (mention as roadmap in interviews; build only if you want more depth)
- **Slice 9 Experimentation** — compare model/prompt/RAG-vs-not, store Experiment records
  with per-run metadata, Streamlit comparison view. Strong "how do you know it got
  better?" answer.
- **Slice 10 FastAPI** — expose the same services as endpoints; services unchanged.
- **Slice 11 New question types** — True/False, Fill-in-Blank, then Essay/Matching/
  Ordering, using the Slice 1 discriminated model (cheap because of that design).

---

## 4. The README (do this last — it does the most interview work)

Ask Claude (normal chat):
> "Read all of docs/ and the codebase. Draft a portfolio README.md for a GenAI/ML
> engineer audience with: a one-line problem statement; the honest framing that this is
> my clean-room reimplementation of a past-company concept (no proprietary code/data);
> an architecture overview; the key design decisions with tradeoffs (from docs/
> DECISIONS.md); a 'built vs roadmapped' section; setup instructions; and placeholders
> for the live demo link, screenshots, my name, and GitHub handle. Keep it accurate to
> what's actually built — no overclaiming."

You fill in name, GitHub, demo link, screenshots.

---

## 5. Interview-day summary

The core slices (2, 4, 5, and 6/7 if built) are where you'll be tested. Before
interviews, make sure you can, in your own words:
1. Explain the provider abstraction and how to add a new LLM/embedding vendor (Slice 2).
2. Explain LLM-as-judge, its failure modes, and rubric-based scoring (Slice 4) — your
   strongest GenAI signal.
3. Explain the human-in-the-loop review + versioning and how it builds dataset quality
   (Slice 5).
4. Explain RAG grounding and traceability if you built 6/7.
5. Walk your `docs/DECISIONS.md` — the why-X-over-Y list is your interview backbone.

Build order recap: docs -> init -> Slice 1 -> 2 -> 3 -> 4 -> 5 -> D -> deploy -> README,
then 6/7/8 optional, Phase 2 as roadmap.

---

## 6. One decision to confirm before Slice 1
This guide assumes **SQLite + local chromadb** for the MVP (right choice for a free
Streamlit Cloud demo). If you'd rather use Postgres/a hosted vector store from day one,
adjust `docs/TECH_DECISIONS.md` and Slice 1's schema step first; everything else is
unchanged.
