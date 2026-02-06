from pydantic_settings import BaseSettings
from typing import Optional
from functools import lru_cache

class Settings(BaseSettings):
    PROJECT_NAME: str = "Research Assistant API"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # MongoDB
    MONGO_URL: str = "mongodb://localhost:27017"
    MONGO_DB_NAME: str = "research_assistant"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Vector DB
    VECTOR_DB_URL: str = "http://localhost:6333"
    VECTOR_DB_API_KEY: Optional[str] = None

    # LLM Keys
    GEMINI_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None

    class Config:
        env_file = ".env"
        case_sensitive = True

@lru_cache()
def get_settings():
    return Settings()

settings = get_settings()
