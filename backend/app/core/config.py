from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # ── MongoDB ──────────────────────────────────────────────────────────────
    MONGODB_URL: str = "mongodb://mongo:27017"
    MONGODB_DB: str = "docutrust"

    # ── Qdrant ───────────────────────────────────────────────────────────────
    QDRANT_HOST: str = "qdrant"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION: str = "documents"

    # ── Gemini ───────────────────────────────────────────────────────────────
    GEMINI_API_KEY: str

    # ── JWT ──────────────────────────────────────────────────────────────────
    SECRET_KEY: str = "change-me-in-production-32chars!!"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    # ── File storage ─────────────────────────────────────────────────────────
    UPLOAD_DIR: str = "/tmp/docutrust_uploads"

    # ── Embedding model ──────────────────────────────────────────────────────
    # all-MiniLM-L6-v2 produces 384-dim vectors — keep VECTOR_SIZE in sync.
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    VECTOR_SIZE: int = 384          # must match EMBEDDING_MODEL output dims

    # ── Cross-encoder grader model ───────────────────────────────────────────
    CROSS_ENCODER_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # ── Chunking ─────────────────────────────────────────────────────────────
    # CHUNK_SIZE is measured in WORDS (the splitter uses text.split()).
    # 300 words ≈ 400-500 tokens for English prose — a safe fit for MiniLM.
    CHUNK_SIZE: int = 300
    CHUNK_OVERLAP: int = 50         # words of overlap between adjacent chunks
    MIN_CHUNK_WORDS: int = 20       # discard chunks shorter than this

    # ── Retrieval ────────────────────────────────────────────────────────────
    TOP_K_RETRIEVAL: int = 5

    # ── Grading threshold ────────────────────────────────────────────────────
    # ms-marco-MiniLM-L-6-v2 raw logits run roughly –10 … +10.
    # After sigmoid:  logit 0  → sigmoid 0.50
    #                 logit 2  → sigmoid 0.88
    # A threshold of 0.35 means sigmoid(logit) ≥ 0.35  →  logit ≥ -0.62
    # which is VERY permissive — almost every chunk passes.
    # Using 0.20 catches genuinely off-topic chunks while allowing
    # marginally relevant ones through for the LLM to handle.
    RELEVANCE_THRESHOLD: float = 0.20

    # ── CRAG control ─────────────────────────────────────────────────────────
    MAX_REWRITE_ITERATIONS: int = 1

    # ── Web fallback ─────────────────────────────────────────────────────────
    DDG_TIMEOUT: int = 8

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()