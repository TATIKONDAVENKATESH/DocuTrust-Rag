# DocuTrust — Enterprise Advanced RAG Platform

Self-correcting Retrieval-Augmented Generation platform for enterprise document intelligence. Built with LangGraph (CRAG pattern), FastAPI, React/TypeScript, MongoDB, and Qdrant.

---

## Architecture Overview

```
Frontend (React 18 + TypeScript + TailwindCSS)   ← Vite, served via nginx on :3000
│
├── Left Panel    — PDF / TXT / DOCX upload + document list (drag-and-drop)
├── Middle Panel  — Real-time CRAG agent execution log (WebSocket streaming)
└── Right Panel   — Chat interface, validated answers, citations with previews

Backend (FastAPI + Python 3.11, async)            ← uvicorn on :8000
│
├── /api/auth        — Register, login, JWT (24 h tokens)
├── /api/documents   — Upload, list, delete; async background ingestion pipeline
├── /api/chat        — REST query endpoint + session management
└── /ws/chat         — WebSocket for real-time CRAG agent log streaming

CRAG Workflow (LangGraph StateGraph)
│
├── Retriever Node        — Embed query → Qdrant ANN search, top-K chunks (per-user filter)
├── Grader Node           — Cross-encoder scores each chunk against the query
├── Decision Router       — Relevant chunks → Generate | Exhausted rewrites → Web fallback | else → Rewrite
├── Query Rewriter Node   — Gemini rewrites query for better retrieval (max 1 iteration by default)
├── Web Fallback Node     — Tavily search when retrieval fully fails
└── Answer Generator Node — Gemini generates cited answer from graded chunks

Storage
├── MongoDB   — Users, documents, chunks metadata, chat sessions & messages
└── Qdrant    — Dense vector index (all-MiniLM-L6-v2, dim=384, per-user payload filter)
```

---

## Technology Stack

| Layer | Technology |
|---|---|
| LLM | Google Gemini 2.5 Flash (`gemini-2.5-flash`) |
| RAG Framework | LangGraph 0.2 — Corrective RAG (CRAG) pattern |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` (384-dim) |
| Reranker / Grader | `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| Web Fallback Search | Tavily (`tavily-python`) |
| Vector DB | Qdrant v1.9.4 |
| Document DB | MongoDB 7 (Motor async driver) |
| Backend | FastAPI 0.111 + Uvicorn (Python 3.11, fully async) |
| PDF / DOCX Parsing | PyMuPDF 1.24 (3-strategy extraction) + python-docx |
| Auth | JWT via `python-jose`, passwords via `passlib[bcrypt]` |
| Frontend | React 18, TypeScript 5, TailwindCSS 3, Vite 8 |
| Frontend extras | Axios, react-dropzone, react-markdown, lucide-react |
| Containers | Docker Compose (mongo, qdrant, backend, frontend services) |

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `GEMINI_API_KEY` | ✅ | — | Google Gemini API key — get from https://aistudio.google.com/app/apikey |
| `TAVILY_API_KEY` | ⚠️ optional | `""` | Tavily search API key — required only if you want web fallback to work |
| `SECRET_KEY` | ✅ | `change-me-in-production-32chars!!` | 32+ char random string for JWT signing |
| `GEMINI_MODEL` | optional | `gemini-2.5-flash` | Override the Gemini model name |
| `MONGODB_URL` | optional | `mongodb://mongo:27017` | MongoDB connection string |
| `MONGODB_DB` | optional | `docutrust` | Database name |
| `QDRANT_HOST` | optional | `qdrant` | Qdrant service hostname |
| `QDRANT_PORT` | optional | `6333` | Qdrant port |
| `QDRANT_COLLECTION` | optional | `documents` | Qdrant collection name |
| `CHUNK_SIZE` | optional | `300` | Words per chunk |
| `CHUNK_OVERLAP` | optional | `50` | Overlapping words between adjacent chunks |
| `MIN_CHUNK_WORDS` | optional | `20` | Discard chunks shorter than this |
| `TOP_K_RETRIEVAL` | optional | `5` | Chunks retrieved per query |
| `RELEVANCE_THRESHOLD` | optional | `0.20` | Cross-encoder score cutoff for relevant chunks |
| `MAX_REWRITE_ITERATIONS` | optional | `1` | How many query rewrites before triggering web fallback |
| `DDG_TIMEOUT` | optional | `8` | Web search timeout in seconds |
| `CORS_ORIGINS` | optional | `*` | Comma-separated allowed CORS origins |

---

## Quick Start (Docker Compose)

```bash
# 1. Clone the repo
git clone <repo-url>
cd docutrust

# 2. Create environment file
cp .env.example .env
# Edit .env — set GEMINI_API_KEY (and optionally TAVILY_API_KEY)

# 3. Build and start all services
docker compose up --build

# 4. Open the app
open http://localhost:3000
```

The first build downloads HuggingFace ML models (~200 MB). Subsequent builds use a cached Docker volume (`hf_cache`), so they are fast.

Services exposed:
- Frontend: http://localhost:3000
- Backend API + docs: http://localhost:8000/docs
- Qdrant dashboard: http://localhost:6333/dashboard
- MongoDB: localhost:27017

---

## Local Development (without Docker)

### Backend

```bash
cd backend

# Python 3.11 required
python3.11 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt

# Spin up MongoDB and Qdrant locally via Docker
docker run -d -p 27017:27017 mongo:7
docker run -d -p 6333:6333 qdrant/qdrant:v1.9.4

# Configure environment
cp ../.env.example .env
# Edit .env — set GEMINI_API_KEY

# Start the API server
uvicorn app.main:app --reload --port 8000
```

On startup the backend pre-loads both ML models (embedding + cross-encoder) into memory so the first query is fast.

### Frontend

```bash
cd frontend
npm install
npm run dev       # starts Vite dev server
# Open http://localhost:3000
```

The Vite dev server proxies `/api` and `/ws` to the backend at `localhost:8000` — no extra config needed.

### Windows (batch helper)

A `setup_local_venv.bat` script is provided for Windows users to bootstrap the backend virtualenv automatically.

---

## CRAG Workflow (Detailed)

```
User Query
    │
    ▼
Retriever Node
    │  embed query (all-MiniLM-L6-v2)
    │  → Qdrant ANN search with per-user payload filter
    │  → top-K chunks (default K=5)
    ▼
Grader Node
    │  cross-encoder/ms-marco-MiniLM-L-6-v2 scores each (query, chunk) pair
    │  avg score logged to agent trace
    │  chunks with score ≥ RELEVANCE_THRESHOLD (default 0.20) kept
    ▼
Decision Router
    ├── relevant chunks found           → Answer Generator
    ├── iteration < MAX_REWRITE_ITERATIONS → Query Rewriter
    └── iteration ≥ MAX_REWRITE_ITERATIONS → Web Fallback Node
         │
         ├── Query Rewriter Node
         │       Gemini rewrites query for better retrieval
         │       iteration counter incremented → back to Retriever
         │
         └── Web Fallback Node
                 Tavily search (requires TAVILY_API_KEY)
                 results injected as synthetic chunks
                 → Answer Generator
    ▼
Answer Generator Node
    │  Gemini prompt strictly grounded in retrieved/web chunks
    │  each source referenced as [Source N]
    │  citations built with filename, page number, chunk ID, relevance score, text preview
    ▼
Response returned with:
    - answer text
    - citations list
    - agent_trace log (every step)
    - confidence score (avg relevance score of chunks used)
    - used_web_fallback flag
```

---

## Document Ingestion Pipeline

Supported formats: **PDF**, **TXT**, **DOCX**

**PDF extraction** uses a 3-strategy cascade per page:
1. Plain text (`get_text("text")`) — fastest, works for standard PDFs
2. Block-level (`get_text("blocks")`) — handles complex layouts
3. Span-level (`get_text("dict")`) — catches text in complex annotations

Pages yielding fewer than `MIN_CHUNK_WORDS` words are skipped with a warning (image-only/scanned pages). OCR is not currently supported for scanned PDFs.

After extraction, text is chunked with a sliding word window (`CHUNK_SIZE`, `CHUNK_OVERLAP`), embedded in batches, and upserted to Qdrant. Chunk metadata (including `user_id`) is stored in MongoDB so retrieval is always isolated per user.

Document status flows: `processing` → `ready` | `error` (with an error message surfaced to the UI).

---

## API Reference

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/api/auth/register` | — | Create account |
| POST | `/api/auth/login` | — | Get JWT token |
| GET | `/api/auth/me` | JWT | Current user info |
| POST | `/api/documents/upload` | JWT | Upload PDF / TXT / DOCX; triggers async ingestion |
| GET | `/api/documents/` | JWT | List user's documents with status |
| DELETE | `/api/documents/{id}` | JWT | Delete document + its Qdrant vectors |
| POST | `/api/chat/query` | JWT | REST query — runs CRAG, returns full response |
| GET | `/api/chat/sessions` | JWT | List user's chat sessions |
| GET | `/api/chat/sessions/{id}/messages` | JWT | Messages in a session |
| WS | `/ws/chat?token=<JWT>` | JWT (query param) | WebSocket — streams CRAG agent logs in real time |
| GET | `/health` | — | Service health + active config values |

Interactive API docs are available at `http://localhost:8000/docs` (Swagger UI).

---

## Notes

- **Scanned PDFs** (image-only) are not supported — text extraction returns nothing for them. A future OCR layer (e.g. `pytesseract`) would be needed.
- **Web fallback** requires a valid `TAVILY_API_KEY`. Without it the fallback node logs an error and the answer generator returns a "no relevant information found" message.
- **HuggingFace models** are cached in a named Docker volume (`hf_cache`) so they survive container restarts without re-downloading.
- **Per-user isolation** is enforced at the Qdrant query level via a payload filter on `user_id`, so users can only retrieve their own documents.
- The `RELEVANCE_THRESHOLD` default was lowered to `0.20` (from `0.5` in earlier iterations) to reduce over-triggering of query rewrites on legitimate documents.