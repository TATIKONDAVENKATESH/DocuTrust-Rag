import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from sentence_transformers import CrossEncoder
from app.core.config import settings

logger = logging.getLogger(__name__)

_GRADER_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="grader")

_model: CrossEncoder = None


def load_cross_encoder() -> None:
    global _model
    logger.info(f"Loading cross-encoder model: {settings.CROSS_ENCODER_MODEL}")
    _model = CrossEncoder(settings.CROSS_ENCODER_MODEL)
    logger.info("Cross-encoder model loaded.")


def get_cross_encoder() -> CrossEncoder:
    global _model
    if _model is None:
        load_cross_encoder()
    return _model


def _grade_sync(query: str, chunks: list[str]) -> list[float]:
    model = get_cross_encoder()
    pairs = [(query, chunk) for chunk in chunks]
    raw_scores = model.predict(pairs)
    sigmoid_scores = (1 / (1 + np.exp(-np.array(raw_scores)))).tolist()

    for i, (raw, sig) in enumerate(zip(raw_scores, sigmoid_scores)):
        status = "PASS" if sig >= settings.RELEVANCE_THRESHOLD else "FAIL"
        logger.info(f"  Chunk {i}: logit={raw:.3f}  sigmoid={sig:.3f}  [{status}]")

    return sigmoid_scores


async def grade_chunks_async(query: str, chunks: list[str]) -> list[float]:
    if not chunks:
        return []
    loop = asyncio.get_running_loop()
    logger.info(f"Grading {len(chunks)} chunks with cross-encoder (dedicated pool)...")
    scores = await loop.run_in_executor(_GRADER_EXECUTOR, _grade_sync, query, chunks)
    logger.info(f"Grading complete. Scores: {[round(s, 2) for s in scores]}")
    return scores


def grade_chunks(query: str, chunks: list[str]) -> list[float]:
    if not chunks:
        return []
    return _grade_sync(query, chunks)