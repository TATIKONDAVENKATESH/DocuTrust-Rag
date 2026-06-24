from sentence_transformers import CrossEncoder
from app.core.config import settings

_model: CrossEncoder = None


def get_cross_encoder() -> CrossEncoder:
    global _model
    if _model is None:
        _model = CrossEncoder(settings.CROSS_ENCODER_MODEL)
    return _model


def grade_chunks(query: str, chunks: list[str]) -> list[float]:
    """Return relevance scores for each chunk against the query."""
    if not chunks:
        return []
    model = get_cross_encoder()
    pairs = [(query, chunk) for chunk in chunks]
    scores = model.predict(pairs)
    # Normalize to [0, 1] via sigmoid approximation
    import numpy as np
    scores = 1 / (1 + np.exp(-scores))
    return scores.tolist()
