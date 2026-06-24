# DocuTrust — Enterprise Advanced RAG Platform

Self-correcting Retrieval-Augmented Generation platform for enterprise document intelligence. Built with LangGraph CRAG, FastAPI, React, MongoDB, and Qdrant.

---

## Architecture

```
Frontend (React + TypeScript + TailwindCSS)
│
├── Left Panel   — PDF/TXT/DOCX upload + document list
├── Middle Panel — Real-time agent execution log (WebSocket)
└── Right Panel  — Chat interface + validated answers + citations

Backend (FastAPI + Python 3.11)
│
├── /api/auth     — Register, login, JWT
├── /api/documents— Upload, list, delete (async ingestion pipeline)
├── /api/chat     — Query endpoint, session management
└── /ws/chat      — WebSocket for real-time CRAG agent logs

CRAG Workflow (LangGraph)
│
├── Retriever Node      — Embed query → search Qdrant top-8
├── Grader Node         — Cross-encoder scores each chunk
├── Decision            — Relevant? → Generate. Not relevant? → Rewrite
├── Query Rewriter Node — Gemini rewrites query for better retrieval
└── Answer Generator    — Gemini generates cited answer from chunks

Databases
├── MongoDB  — Users, chat sessions, messages, interaction traces, chunk metadata
└── Qdrant   — Dense vector index (sentence-transformers/all-MiniLM-L6-v2, dim=384)
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | ✅ | Google Gemini API key (get from https://aistudio.google.com/app/apikey) |
| `SECRET_KEY` | ✅ | 32+ char random string for JWT signing |
| `MONGODB_URL` | optional | Defaults to `mongodb://mongo:27017` |
| `QDRANT_HOST` | optional | Defaults to `qdrant` |
| `QDRANT_PORT` | optional | Defaults to `6333` |
| `CHUNK_SIZE` | optional | Words per chunk, default `512` |
| `CHUNK_OVERLAP` | optional | Overlapping words, default `64` |
| `TOP_K_RETRIEVAL` | optional | Chunks retrieved per query, default `8` |
| `RELEVANCE_THRESHOLD` | optional | Cross-encoder score cutoff, default `0.5` |

---

## Quick Start (Docker Compose)

```bash
# 1. Clone and enter the repo
git clone <repo-url>
cd docutrust

# 2. Create environment file
cp .env.example .env
# Edit .env — set your GEMINI_API_KEY

# 3. Build and start all services
docker compose up --build

# 4. Open the app
open http://localhost:3000
```

The first build downloads the ML models (~200MB). Subsequent builds are fast.

---

## Local Development (without Docker)

### Backend

```bash
cd backend

# Create virtualenv (Python 3.11)
python3.11 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy and configure env
cp ../.env.example .env
# Edit .env

# Start MongoDB and Qdrant (via Docker)
docker run -d -p 27017:27017 mongo:7
docker run -d -p 6333:6333 qdrant/qdrant:v1.9.4

# Run the API server
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# Open http://localhost:3000
```

---

## CRAG Workflow

```
START
  │
  ▼
Retriever Agent
  │  embed query → Qdrant search → top-8 chunks
  ▼
Grading Agent
  │  cross-encoder/ms-marco-MiniLM-L-6-v2 scores each chunk
  ▼
Decision
  ├── score ≥ 0.5 (relevant chunks found)
  │     └──→ Answer Generator → END
  └── score < 0.5 (poor retrieval)
        └──→ Query Rewriter (Gemini)
              └──→ Retriever Agent (retry, max 2 iterations)
                    └──→ Grading Agent
                          └──→ Answer Generator → END
```

Every answer includes:
- The generated response grounded in document chunks
- A Sources block listing filename, page number, and chunk ID

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/auth/register` | Create account |
| POST | `/api/auth/login` | Get JWT token |
| GET | `/api/auth/me` | Current user |
| POST | `/api/documents/upload` | Upload PDF/TXT/DOCX |
| GET | `/api/documents/` | List documents |
| DELETE | `/api/documents/{id}` | Delete document + vectors |
| POST | `/api/chat/query` | Submit query (REST) |
| GET | `/api/chat/sessions` | List chat sessions |
| GET | `/api/chat/sessions/{id}/messages` | Get messages in session |
| WS | `/ws/chat?token=JWT` | Real-time CRAG with streaming logs |

---

## Technology Stack

| Layer | Technology |
|---|---|
| LLM | Google Gemini 1.5 Flash |
| RAG Framework | LangGraph (CRAG pattern) |
| Embeddings | sentence-transformers/all-MiniLM-L6-v2 |
| Reranker | cross-encoder/ms-marco-MiniLM-L-6-v2 |
| Vector DB | Qdrant |
| Document DB | MongoDB |
| Backend | FastAPI (Python 3.11, async) |
| Frontend | React 18, TypeScript, TailwindCSS |
| Auth | JWT (python-jose) |
| Containers | Docker Compose |
