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