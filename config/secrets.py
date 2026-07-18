import tomllib
from pathlib import Path

from pydantic import BaseModel

SECRETS_PATH = Path(__file__).parent / "secrets.toml"
EXAMPLE_SECRETS_PATH = Path(__file__).parent / "secrets.example.toml"


class Secrets(BaseModel):
    groq_api_key: str
    cohere_api_key: str | None = None


def load_secrets(path: Path | str | None = None) -> Secrets:
    resolved_path = Path(path) if path is not None else SECRETS_PATH
    if not resolved_path.exists():
        raise FileNotFoundError(
            f"No secrets file at {resolved_path}. Copy {EXAMPLE_SECRETS_PATH} to "
            f"{resolved_path} and fill in your own API key(s)."
        )
    data = tomllib.loads(resolved_path.read_text())
    return Secrets(**data)
