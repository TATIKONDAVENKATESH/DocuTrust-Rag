from sentence_transformers import CrossEncoder
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

_model: CrossEncoder = None


def load_cross_encoder() -> None:
    """
    Eagerly load the cross-encoder model at startup.
    Call from FastAPI lifespan to avoid cold-start delays on first query.
    """
    global _model
    logger.info(f"Loading cross-encoder model: {settings.CROSS_ENCODER_MODEL}")
    _model = CrossEncoder(settings.CROSS_ENCODER_MODEL)
    logger.info("Cross-encoder model loaded.")


def get_cross_encoder() -> CrossEncoder:
    global _model
    if _model is None:
        load_cross_encoder()
    return _model


def grade_chunks(query: str, chunks: list[str]) -> list[float]:
    """Return relevance scores for each chunk against the query."""
    if not chunks:
        return []
    model = get_cross_encoder()
    pairs = [(query, chunk) for chunk in chunks]
    scores = model.predict(pairs)
    # Normalize to [0, 1] via sigmoid
    import numpy as np
    scores = 1 / (1 + np.exp(-scores))
    return scores.tolist()
