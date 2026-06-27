import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.services.grader import load_cross_encoder, _GRADER_EXECUTOR
from app.db.mongodb import connect_db, close_db
from app.db.qdrant import connect_qdrant, close_qdrant
from app.api import auth, documents, chat, websocket
from app.core.config import settings
from app.services.embedding import load_embedding_model
import asyncio

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting DocuTrust API…")
    await connect_db()
    await connect_qdrant()

    loop = asyncio.get_running_loop()

    # Preload embedding model (always needed, ~10-30s on first Docker start)
    logger.info("Pre-loading embedding model…")

    await loop.run_in_executor(None, load_embedding_model)

    logger.info("Pre-loading cross-encoder model…")

    await loop.run_in_executor(_GRADER_EXECUTOR, load_cross_encoder)

    logger.info("All services connected and models loaded.")
    yield

    await close_db()
    await close_qdrant()
    logger.info("Shutdown complete.")

app = FastAPI(
    title="DocuTrust API",
    description="Enterprise Advanced RAG Platform with Automated Self-Correction",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(websocket.router)


@app.get("/health", tags=["meta"])
async def health():
    return {
        "status": "ok",
        "version": "1.0.0",
        "relevance_threshold": settings.RELEVANCE_THRESHOLD,
        "max_rewrite_iterations": settings.MAX_REWRITE_ITERATIONS,
        "ddg_timeout": settings.DDG_TIMEOUT,
    }