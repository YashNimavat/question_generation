import pytest

from config import secrets as secrets_module
from embeddings.cohere_provider import CohereProvider
from embeddings.registry import get_embedding_provider


@pytest.fixture
def secrets_file(tmp_path, monkeypatch):
    path = tmp_path / "secrets.toml"
    path.write_text('groq_api_key = "test-key"\ncohere_api_key = "test-cohere-key"\n')
    monkeypatch.setattr(secrets_module, "SECRETS_PATH", path)
    return path


def test_get_embedding_provider_defaults_to_cohere(secrets_file):
    provider = get_embedding_provider()

    assert isinstance(provider, CohereProvider)


def test_get_embedding_provider_explicit_cohere(secrets_file):
    provider = get_embedding_provider("cohere")

    assert isinstance(provider, CohereProvider)


def test_get_embedding_provider_unknown_provider_raises(secrets_file):
    with pytest.raises(ValueError, match="Unknown embedding provider"):
        get_embedding_provider("openai")


def test_get_embedding_provider_missing_cohere_key_raises(tmp_path, monkeypatch):
    path = tmp_path / "secrets.toml"
    path.write_text('groq_api_key = "test-key"\n')
    monkeypatch.setattr(secrets_module, "SECRETS_PATH", path)

    with pytest.raises(ValueError, match="No cohere_api_key configured"):
        get_embedding_provider("cohere")
