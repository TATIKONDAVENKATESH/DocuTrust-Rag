from __future__ import annotations

import asyncio
import logging
from typing import List, Optional, TypedDict, Callable, Awaitable

from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.config import settings
from app.db.qdrant import get_qdrant
from app.models.schemas import Citation
from app.services.embedding import embed_query
from app.services.grader import grade_chunks

logger = logging.getLogger(__name__)

MAX_REWRITE_ITERATIONS = 2


# ── State ────────────────────────────────────────────────────────────────────

class RAGState(TypedDict):
    query: str
    retrieved_chunks: List[dict]
    scores: List[float]
    relevant_chunks: List[dict]
    rewritten_query: Optional[str]
    answer: str
    citations: List[Citation]
    agent_logs: List[str]
    iteration: int


# ── Helpers ──────────────────────────────────────────────────────────────────

async def _retrieve(query: str) -> List[dict]:
    qdrant = get_qdrant()
    loop = asyncio.get_running_loop()
    vector = await loop.run_in_executor(None, embed_query, query)
    results = await qdrant.search(
        collection_name=settings.QDRANT_COLLECTION,
        query_vector=vector,
        limit=settings.TOP_K_RETRIEVAL,
        with_payload=True,
    )
    return [r.payload for r in results]


def _get_llm() -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model="gemini-1.5-flash",
        google_api_key=settings.GEMINI_API_KEY,
        temperature=0.2,
    )


# ── Nodes ────────────────────────────────────────────────────────────────────

async def retriever_node(state: RAGState) -> dict:
    query = state.get("rewritten_query") or state["query"]
    logs = list(state["agent_logs"])
    logs.append("Retrieving chunks...")
    chunks = await _retrieve(query)
    logs.append(f"Retrieved {len(chunks)} chunks.")
    return {"retrieved_chunks": chunks, "agent_logs": logs}


async def grader_node(state: RAGState) -> dict:
    query = state.get("rewritten_query") or state["query"]
    chunks = state["retrieved_chunks"]
    logs = list(state["agent_logs"])
    logs.append("Running relevance grading...")

    if not chunks:
        logs.append("No chunks to grade.")
        return {"scores": [], "relevant_chunks": [], "agent_logs": logs}

    loop = asyncio.get_running_loop()
    texts = [c["text"] for c in chunks]
    scores: List[float] = await loop.run_in_executor(None, grade_chunks, query, texts)

    avg_score = sum(scores) / len(scores) if scores else 0.0
    logs.append(f"Relevance score: {avg_score:.2f}")

    relevant = [c for c, s in zip(chunks, scores) if s >= settings.RELEVANCE_THRESHOLD]
    logs.append(f"Relevant chunks after grading: {len(relevant)}")

    return {"scores": scores, "relevant_chunks": relevant, "agent_logs": logs}


async def query_rewriter_node(state: RAGState) -> dict:
    original_query = state["query"]
    logs = list(state["agent_logs"])
    logs.append("Rewriting query for better retrieval...")

    llm = _get_llm()
    prompt = (
        f"The following search query did not produce sufficiently relevant document chunks.\n"
        f"Original query: {original_query}\n\n"
        f"Rewrite the query to be more specific and retrieval-friendly. "
        f"Return ONLY the rewritten query text, nothing else."
    )
    try:
        response = await llm.ainvoke(prompt)
        rewritten = response.content.strip()
    except Exception as exc:
        logger.warning(f"Query rewrite failed: {exc}. Using original query.")
        rewritten = original_query

    logs.append(f"Rewritten query: {rewritten}")

    return {
        "rewritten_query": rewritten,
        "agent_logs": logs,
        "iteration": state.get("iteration", 0) + 1,
    }


async def answer_generator_node(state: RAGState) -> dict:
    query = state.get("rewritten_query") or state["query"]
    relevant = state["relevant_chunks"]
    logs = list(state["agent_logs"])
    logs.append("Generating answer...")

    if not relevant:
        answer = (
            "I could not find sufficiently relevant information in the uploaded documents "
            "to answer your question. Please upload documents that cover this topic."
        )
        logs.append("Answer generated (no relevant chunks found).")
        return {"answer": answer, "citations": [], "agent_logs": logs}

    # Build context block
    context_parts = []
    for i, chunk in enumerate(relevant, start=1):
        context_parts.append(
            f"[Source {i}] File: {chunk['filename']}, "
            f"Page: {chunk.get('page_number', 'N/A')}\n{chunk['text']}"
        )
    context = "\n\n".join(context_parts)

    prompt = (
        "You are a precise enterprise document assistant. Answer the question using ONLY "
        "the provided document excerpts. Do not speculate beyond what the documents say.\n\n"
        f"Question: {query}\n\n"
        f"Document Excerpts:\n{context}\n\n"
        "Provide a thorough answer based strictly on the excerpts above. "
        "Reference sources by their [Source N] labels where appropriate."
    )

    llm = _get_llm()
    try:
        response = await llm.ainvoke(prompt)
        answer_text = response.content.strip()
    except Exception as exc:
        logger.exception(f"Answer generation failed: {exc}")
        answer_text = "An error occurred while generating the answer. Please try again."

    citations = [
        Citation(
            filename=chunk["filename"],
            page_number=chunk.get("page_number"),
            chunk_id=str(chunk.get("chunk_id", chunk.get("chunk_index", i))),
        )
        for i, chunk in enumerate(relevant)
    ]

    logs.append("Answer generated.")
    return {"answer": answer_text, "citations": citations, "agent_logs": logs}


# ── Routing ──────────────────────────────────────────────────────────────────

def should_rewrite(state: RAGState) -> str:
    relevant = state.get("relevant_chunks", [])
    iteration = state.get("iteration", 0)
    if relevant or iteration >= MAX_REWRITE_ITERATIONS:
        return "generate"
    return "rewrite"


# ── Graph Assembly ────────────────────────────────────────────────────────────

def build_crag_graph():
    builder = StateGraph(RAGState)
    builder.add_node("retriever", retriever_node)
    builder.add_node("grader", grader_node)
    builder.add_node("rewriter", query_rewriter_node)
    builder.add_node("generator", answer_generator_node)
    builder.set_entry_point("retriever")
    builder.add_edge("retriever", "grader")
    builder.add_conditional_edges(
        "grader",
        should_rewrite,
        {"generate": "generator", "rewrite": "rewriter"},
    )
    builder.add_edge("rewriter", "retriever")
    builder.add_edge("generator", END)
    return builder.compile()


_graph = None


def get_crag_graph():
    global _graph
    if _graph is None:
        _graph = build_crag_graph()
    return _graph


# ── Public Runner ─────────────────────────────────────────────────────────────

async def run_crag(
    query: str,
    log_callback: Optional[Callable[[str], Awaitable[None]]] = None,
) -> dict:
    """
    Execute the CRAG graph and return {answer, citations, agent_logs}.
    log_callback receives each new log line as it is emitted by agent nodes.
    """
    graph = get_crag_graph()
    initial_state: RAGState = {
        "query": query,
        "retrieved_chunks": [],
        "scores": [],
        "relevant_chunks": [],
        "rewritten_query": None,
        "answer": "",
        "citations": [],
        "agent_logs": [],
        "iteration": 0,
    }

    seen_logs: int = 0
    # Accumulate full state across streaming steps
    accumulated: dict = dict(initial_state)

    async for step in graph.astream(initial_state):
        # Each step is {node_name: partial_state_dict}
        for node_name, partial in step.items():
            # Merge partial state into accumulated
            accumulated.update(partial)
            # Stream any new log lines via callback
            current_logs: List[str] = accumulated.get("agent_logs", [])
            for log_line in current_logs[seen_logs:]:
                if log_callback:
                    try:
                        await log_callback(log_line)
                    except Exception:
                        pass
            seen_logs = len(current_logs)

    return {
        "answer": accumulated.get("answer", ""),
        "citations": accumulated.get("citations", []),
        "agent_logs": accumulated.get("agent_logs", []),
    }