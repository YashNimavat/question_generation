from pydantic import BaseModel


class Settings(BaseModel):
    default_llm_provider: str = "groq"
    default_llm_model: str = "llama-3.3-70b-versatile"
    default_judge_model: str = "llama-3.1-8b-instant"


settings = Settings()
