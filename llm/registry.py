from config.secrets import load_secrets
from config.settings import settings
from llm.base import LLMProvider
from llm.groq_provider import GroqProvider


def get_llm_provider(provider_name: str | None = None) -> LLMProvider:
    provider_name = provider_name or settings.default_llm_provider
    if provider_name == "groq":
        secrets = load_secrets()
        return GroqProvider(api_key=secrets.groq_api_key)
    raise ValueError(f"Unknown LLM provider: {provider_name!r}")
