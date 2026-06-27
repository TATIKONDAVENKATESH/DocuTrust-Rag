from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # MongoDB
    MONGODB_URL: str = "mongodb://mongo:27017"
    MONGODB_DB: str = "docutrust"

    # Qdrant
    QDRANT_HOST: str = "qdrant"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION: str = "documents"

    GEMINI_API_KEY: str

    # JWT
    SECRET_KEY: str = "change-me-in-production-32chars!!"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    # App
    UPLOAD_DIR: str = "/tmp/docutrust_uploads"
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"

    CROSS_ENCODER_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 64

    TOP_K_RETRIEVAL: int = 5

    RELEVANCE_THRESHOLD: float = 0.35

    MAX_REWRITE_ITERATIONS: int = 1

    DDG_TIMEOUT: int = 8

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()