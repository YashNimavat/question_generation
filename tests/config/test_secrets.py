import pytest

from config.secrets import load_secrets


def test_load_secrets_reads_toml_file(tmp_path):
    path = tmp_path / "secrets.toml"
    path.write_text('groq_api_key = "abc123"\n')

    secrets = load_secrets(path)

    assert secrets.groq_api_key == "abc123"


def test_load_secrets_missing_file_raises_clear_error(tmp_path):
    path = tmp_path / "does_not_exist.toml"

    with pytest.raises(FileNotFoundError, match="secrets.example.toml|does_not_exist.toml"):
        load_secrets(path)
