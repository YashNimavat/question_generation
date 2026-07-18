from config.secrets import load_secrets
from config.settings import settings
from embeddings.base import EmbeddingProvider
from embeddings.cohere_provider import CohereProvider


def get_embedding_provider(provider_name: str | None = None) -> EmbeddingProvider:
    provider_name = provider_name or settings.default_embedding_provider
    if provider_name == "cohere":
        secrets = load_secrets()
        if not secrets.cohere_api_key:
            raise ValueError(
                "No cohere_api_key configured in config/secrets.toml -- add one before "
                "using the Cohere embedding provider."
            )
        return CohereProvider(api_key=secrets.cohere_api_key)
    raise ValueError(f"Unknown embedding provider: {provider_name!r}")
