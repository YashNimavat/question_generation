import pytest

from config import secrets as secrets_module
from db.connection import init_db


@pytest.fixture(autouse=True)
def _no_real_secrets(tmp_path, monkeypatch):
    # get_llm_provider()/get_embedding_provider() (llm/registry.py,
    # embeddings/registry.py) build a REAL provider from config/secrets.toml
    # whenever a caller passes provider=None -- that's correct production
    # behavior, but it means any test that doesn't explicitly inject a Fake
    # provider silently falls through to real credentials on the dev machine,
    # making real (billed) network calls and, for embeddings, writing
    # real-dimension vectors into the shared local chroma_data/ dir where they
    # corrupt any other test using fake low-dimensional vectors. This has
    # already bitten multiple test files individually (services/test_generation.py,
    # services/test_dedup.py, services/test_experiment.py, app/test_documents_page.py,
    # app/test_experiments_page.py) -- hoisting the same isolation here so every
    # test gets it by default, with no per-file opt-in required. A groq_api_key is
    # still required (config.secrets.Secrets validates it as non-optional), so it's
    # a harmless fake value; cohere_api_key is deliberately omitted so
    # get_embedding_provider() fails closed (ValueError) instead of reaching Cohere.
    secrets_path = tmp_path / "secrets.toml"
    secrets_path.write_text('groq_api_key = "test-key"\n')
    monkeypatch.setattr(secrets_module, "SECRETS_PATH", secrets_path)


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "test.db"
    init_db(path)
    return path
