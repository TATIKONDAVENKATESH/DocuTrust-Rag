from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional, TypedDict, Callable, Awaitable

from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.config import settings
from app.db.qdrant import get_qdrant
from app.models.schemas import Citation
from app.services.embedding import embed_query
from app.services.grader import grade_chunks_async
from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)

_DDG_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ddg")

_EMBED_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="embed")

def _get_llm() -> ChatGoogleGenerativeAI:
    from google.generativeai.types import HarmCategory, HarmBlockThreshold

    safety_settings = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }

    return ChatGoogleGenerativeAI(
        model="gemini-1.5-flash",
        google_api_key=settings.GEMINI_API_KEY,
        temperature=0.2,
        safety_settings=safety_settings,
        convert_system_message_to_human=True,
    )

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
    used_web_fallback: bool

async def _retrieve(query: str) -> List[dict]:
    qdrant = get_qdrant()
    loop = asyncio.get_running_loop()
    vector = await loop.run_in_executor(_EMBED_EXECUTOR, embed_query, query)
    results = await qdrant.search(
        collection_name=settings.QDRANT_COLLECTION,
        query_vector=vector,
        limit=settings.TOP_K_RETRIEVAL,
        with_payload=True,
    )
    return [r.payload for r in results]


def _ensure_citations(raw: list) -> List[Citation]:
    result = []
    for item in raw:
        if isinstance(item, Citation):
            result.append(item)
        elif isinstance(item, dict):
            result.append(Citation(**item))
    return result

async def _invoke_llm_safe(llm: ChatGoogleGenerativeAI, prompt: str) -> str:
    try:
        response = await llm.ainvoke(prompt)
        content = response.content
        if content is None or (isinstance(content, str) and not content.strip()):
            raise RuntimeError(
                "Gemini returned an empty response. "
                "This usually means the content was blocked by safety filters "
                "or the API key quota was exceeded."
            )
        return content.strip()
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"Gemini API call failed: {exc}") from exc

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

    texts = [c["text"] for c in chunks]
    scores: List[float] = await grade_chunks_async(query, texts)

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
        rewritten = await _invoke_llm_safe(llm, prompt)
    except Exception as exc:
        logger.warning(f"Query rewrite failed: {exc}. Using original query.")
        rewritten = original_query

    logs.append(f"Rewritten query: {rewritten}")
    return {
        "rewritten_query": rewritten,
        "agent_logs": logs,
        "iteration": state.get("iteration", 0) + 1,
    }


async def web_fallback_node(state: RAGState) -> dict:
    query = state.get("rewritten_query") or state["query"]
    logs = list(state["agent_logs"])
    logs.append("No relevant document chunks found. Falling back to web search...")

    web_chunks: List[dict] = []
    try:

        loop = asyncio.get_running_loop()

        def _ddg_search() -> list:
            with DDGS(timeout=settings.DDG_TIMEOUT) as ddgs:
                return list(ddgs.text(query, max_results=5))

        results = await loop.run_in_executor(_DDG_EXECUTOR, _ddg_search)

        for i, r in enumerate(results):
            snippet = r.get("body", "").strip()
            url = r.get("href", "")
            title = r.get("title", f"Web result {i + 1}")
            if not snippet:
                continue
            web_chunks.append({
                "chunk_id": f"web-{i}",
                "document_id": "web",
                "filename": f"Web: {url}",
                "text": f"{title}\n{snippet}",
                "page_number": None,
                "chunk_index": i,
            })

        logs.append(f"Web search returned {len(web_chunks)} results.")
    except Exception as exc:
        logger.warning(f"Web fallback search failed: {exc}")
        logs.append(f"Web search failed: {exc}")

    return {
        "relevant_chunks": web_chunks,
        "agent_logs": logs,
        "used_web_fallback": True,
    }

async def answer_generator_node(state: RAGState) -> dict:
    query = state.get("rewritten_query") or state["query"]
    relevant = state["relevant_chunks"]
    logs = list(state["agent_logs"])
    logs.append("Generating answer...")

    if not relevant:
        answer = (
            "I could not find sufficiently relevant information in the uploaded documents "
            "or via web search to answer your question."
        )
        logs.append("Answer generated (no relevant chunks found).")
        return {"answer": answer, "citations": [], "agent_logs": logs}

    context_parts = []
    for i, chunk in enumerate(relevant, start=1):
        context_parts.append(
            f"[Source {i}] File: {chunk['filename']}, "
            f"Page: {chunk.get('page_number', 'N/A')}\n{chunk['text']}"
        )
    context = "\n\n".join(context_parts)

    used_web = state.get("used_web_fallback", False)
    source_note = (
        "These excerpts are from web search results because no sufficiently relevant "
        "document chunks were found. "
        if used_web
        else ""
    )

    prompt = (
        "You are a precise enterprise document assistant. Answer the question using ONLY "
        f"the provided excerpts. {source_note}Do not speculate beyond what the sources say.\n\n"
        f"Question: {query}\n\n"
        f"Excerpts:\n{context}\n\n"
        "Provide a thorough answer based strictly on the excerpts above. "
        "Reference sources by their [Source N] labels where appropriate."
    )

    llm = _get_llm()
    try:
        answer_text = await _invoke_llm_safe(llm, prompt)
        logs.append("Answer generated.")
    except Exception as exc:
        logger.exception(f"Answer generation failed: {exc}")
        answer_text = (
            f"Answer generation failed: {exc}. "
            "Check your GEMINI_API_KEY and API quota."
        )
        logs.append(f"Answer generation failed: {exc}")

    citations = [
        Citation(
            filename=chunk["filename"],
            page_number=chunk.get("page_number"),
            chunk_id=str(chunk.get("chunk_id", chunk.get("chunk_index", i))),
        )
        for i, chunk in enumerate(relevant)
    ]

    return {"answer": answer_text, "citations": citations, "agent_logs": logs}

def should_rewrite_or_fallback(state: RAGState) -> str:
    relevant = state.get("relevant_chunks", [])
    iteration = state.get("iteration", 0)

    if relevant:
        return "generate"
    if iteration >= settings.MAX_REWRITE_ITERATIONS:
        return "web_fallback"
    return "rewrite"

def build_crag_graph():
    builder = StateGraph(RAGState)
    builder.add_node("retriever", retriever_node)
    builder.add_node("grader", grader_node)
    builder.add_node("rewriter", query_rewriter_node)
    builder.add_node("web_fallback", web_fallback_node)
    builder.add_node("generator", answer_generator_node)

    builder.set_entry_point("retriever")
    builder.add_edge("retriever", "grader")
    builder.add_conditional_edges(
        "grader",
        should_rewrite_or_fallback,
        {
            "generate": "generator",
            "rewrite": "rewriter",
            "web_fallback": "web_fallback",
        },
    )
    builder.add_edge("rewriter", "retriever")
    builder.add_edge("web_fallback", "generator")
    builder.add_edge("generator", END)
    return builder.compile()

_graph = None

def get_crag_graph():
    global _graph
    if _graph is None:
        _graph = build_crag_graph()
    return _graph

async def run_crag(
    query: str,
    log_callback: Optional[Callable[[str], Awaitable[None]]] = None,
) -> dict:
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
        "used_web_fallback": False,
    }

    seen_logs: int = 0
    accumulated: dict = dict(initial_state)

    async for step in graph.astream(initial_state):
        for _node_name, partial in step.items():
            accumulated.update(partial)
            current_logs: List[str] = accumulated.get("agent_logs", [])
            for log_line in current_logs[seen_logs:]:
                if log_callback:
                    try:
                        await log_callback(log_line)
                    except Exception:
                        pass
            seen_logs = len(current_logs)

    raw_citations = accumulated.get("citations", [])
    citations = _ensure_citations(raw_citations)

    return {
        "answer": accumulated.get("answer", ""),
        "citations": citations,
        "agent_logs": accumulated.get("agent_logs", []),
    }