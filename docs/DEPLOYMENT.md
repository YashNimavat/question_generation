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