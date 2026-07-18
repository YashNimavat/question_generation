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
- Python 3.12.8, package manager `uv`.
- Data models: Pydantic. DB access via a repository layer, never raw SQL in the UI.
- Prompts live in `prompts/` as versioned files; reference by version string.
- A test for every service function and every LLM-judge before moving on.
- Update the relevant `docs/` file whenever architecture changes.

## Commands
- Install: `uv sync`
- Run app: `uv run streamlit run app/main.py`
- Test: `uv run pytest`