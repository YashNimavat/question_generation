# Tech Decisions (locked for MVP)

## Stack
- Python 3.12.8, `uv`
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