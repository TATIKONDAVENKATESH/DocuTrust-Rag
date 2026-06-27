import fitz  # PyMuPDF
import docx
from pathlib import Path
from typing import List, Tuple
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


def extract_text_with_pages(file_path: str, file_type: str) -> List[Tuple[str, int]]:
    """Return list of (page_text, page_number) tuples. page_number is 1-based."""
    ext = file_type.lower().lstrip(".")
    if ext == "pdf":
        return _extract_pdf(file_path)
    elif ext in ("txt", "text"):
        return _extract_txt(file_path)
    elif ext == "docx":
        return _extract_docx(file_path)
    else:
        raise ValueError(f"Unsupported file type: {file_type}")


def _extract_pdf(path: str) -> List[Tuple[str, int]]:
    pages = []
    try:
        doc = fitz.open(path)
    except Exception as exc:
        logger.error(f"PyMuPDF failed to open PDF '{path}': {exc}")
        return []

    for page_num, page in enumerate(doc, start=1):
        text = ""

        # Strategy 1: plain text extraction (fastest, works on text-based PDFs)
        try:
            raw = page.get_text("text")
            text = _sanitize(raw)
        except Exception as exc:
            logger.warning(f"Page {page_num} 'text' extraction failed: {exc}")

        # Strategy 2: block-level extraction (more robust for complex layouts)
        if not text or len(text.split()) < settings.MIN_CHUNK_WORDS:
            try:
                blocks = page.get_text("blocks")  # [(x0,y0,x1,y1,text,block_no,block_type), ...]
                # block_type 0 = text, 1 = image — skip images
                text_blocks = [b[4] for b in blocks if len(b) >= 5 and b[4].strip()]
                candidate = _sanitize(" ".join(text_blocks))
                if len(candidate.split()) > len(text.split()):
                    text = candidate
            except Exception as exc:
                logger.warning(f"Page {page_num} 'blocks' extraction failed: {exc}")

        # Strategy 3: dict-based — catches text in complex annotations
        if not text or len(text.split()) < settings.MIN_CHUNK_WORDS:
            try:
                page_dict = page.get_text("dict")
                spans = []
                for block in page_dict.get("blocks", []):
                    if block.get("type") != 0:     # 0 = text block
                        continue
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            s = span.get("text", "").strip()
                            if s:
                                spans.append(s)
                candidate = _sanitize(" ".join(spans))
                if len(candidate.split()) > len(text.split()):
                    text = candidate
            except Exception as exc:
                logger.warning(f"Page {page_num} 'dict' extraction failed: {exc}")

        if text and len(text.split()) >= settings.MIN_CHUNK_WORDS:
            pages.append((text, page_num))
        else:
            logger.warning(
                f"Page {page_num} of '{path}' yielded no usable text "
                f"(possibly a scanned/image-only page)."
            )

    doc.close()

    if not pages:
        logger.warning(
            f"PDF '{path}' produced zero text pages. "
            "It may be a scanned image-only PDF — OCR is required for those."
        )
    return pages


def _sanitize(text: str) -> str:
    """Remove null bytes and control characters, collapse whitespace."""
    if not text:
        return ""
    text = text.replace("\x00", "")
    # Keep printable characters + common whitespace
    cleaned = "".join(
        ch if (ch >= " " or ch in "\t\n\r") else " "
        for ch in text
    )
    # Collapse multiple blank lines into one
    import re
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _extract_txt(path: str) -> List[Tuple[str, int]]:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read().strip()
    return [(content, 1)] if content else []


def _extract_docx(path: str) -> List[Tuple[str, int]]:
    doc = docx.Document(path)
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    full_text = "\n".join(paragraphs)
    return [(full_text, 1)] if full_text else []


def chunk_text(text: str, chunk_size: int, overlap: int) -> List[str]:
    """
    Split *text* into overlapping word-based chunks.

    Args:
        text:       Input text string.
        chunk_size: Maximum number of words per chunk (from settings.CHUNK_SIZE).
        overlap:    Number of words shared between consecutive chunks.

    Returns:
        List of non-empty chunk strings that meet the minimum word threshold.
    """
    words = text.split()
    if not words:
        return []

    chunks: List[str] = []
    start = 0
    step = max(chunk_size - overlap, 1)   # prevent infinite loop if overlap ≥ chunk_size

    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk = " ".join(words[start:end])
        # Only keep chunks that meet the minimum length
        if len(words[start:end]) >= settings.MIN_CHUNK_WORDS:
            chunks.append(chunk)
        start += step
        if end == len(words):
            break

    return chunks