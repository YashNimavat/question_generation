import pytest

from config import secrets as secrets_module
from llm.groq_provider import GroqProvider
from llm.registry import get_llm_provider


@pytest.fixture
def secrets_file(tmp_path, monkeypatch):
    path = tmp_path / "secrets.toml"
    path.write_text('groq_api_key = "test-key"\n')
    monkeypatch.setattr(secrets_module, "SECRETS_PATH", path)
    return path


def test_get_llm_provider_defaults_to_groq(secrets_file):
    provider = get_llm_provider()

    assert isinstance(provider, GroqProvider)


def test_get_llm_provider_explicit_groq(secrets_file):
    provider = get_llm_provider("groq")

    assert isinstance(provider, GroqProvider)


def test_get_llm_provider_unknown_provider_raises(secrets_file):
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        get_llm_provider("openai")
