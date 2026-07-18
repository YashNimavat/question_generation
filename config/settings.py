from pydantic import BaseModel


class Settings(BaseModel):
    default_llm_provider: str = "groq"
    default_llm_model: str = "llama-3.3-70b-versatile"
    default_judge_model: str = "llama-3.1-8b-instant"
    default_embedding_provider: str = "cohere"
    default_embedding_model: str = "embed-english-v3.0"
    chroma_persist_dir: str = "chroma_data"
    dedup_hard_threshold: float = 0.05
    dedup_soft_threshold: float = 0.15


settings = Settings()
