from sentence_transformers import SentenceTransformer
from app.core.config import settings
import numpy as np
import logging

logger = logging.getLogger(__name__)

_model: SentenceTransformer = None

def load_embedding_model() -> None:
    global _model
    logger.info(f"Loading embedding model: {settings.EMBEDDING_MODEL}")
    _model = SentenceTransformer(settings.EMBEDDING_MODEL)
    logger.info("Embedding model loaded.")

def get_embedding_model() -> SentenceTransformer:
    global _model
    if _model is None:
        # Fallback for tests / direct invocation outside FastAPI lifespan
        load_embedding_model()
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    model = get_embedding_model()
    embeddings = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
    return embeddings.tolist()


def embed_query(query: str) -> list[float]:
    return embed_texts([query])[0]
