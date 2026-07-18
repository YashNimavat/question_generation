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
Slice 10  FastAPI over the same services (for external clients)          [done]
Slice 11  New question types (True/False, Fill-in-Blank, then Essay/Matching/Ordering)

## Deferred always-until-needed
Postgres, hosted vector store, monitoring dashboards, LangSmith/RAGAS, multi-tenant.