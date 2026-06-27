import fitz  # PyMuPDF
import docx
from pathlib import Path
from typing import List, Tuple
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


def extract_text_with_pages(file_path: str, file_type: str) -> List[Tuple[str, int]]:
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

    for i, page in enumerate(doc, start=1):
        text = ""
        try:
            raw = page.get_text("text")
            text = _sanitize(raw)
        except Exception as exc:
            logger.warning(f"Page {i} 'text' extraction failed: {exc}")

        if not text:
            try:
                blocks = page.get_text("blocks")  # list of (x0,y0,x1,y1,text,...)
                text = _sanitize(" ".join(b[4] for b in blocks if b[4].strip()))
            except Exception as exc:
                logger.warning(f"Page {i} 'blocks' extraction failed: {exc}")

        if text:
            pages.append((text, i))
        else:
            logger.warning(f"Page {i} of '{path}' yielded no extractable text (possibly scanned image).")

    doc.close()

    if not pages:
        logger.warning(
            f"PDF '{path}' produced zero text pages. "
            "It may be a scanned image-only PDF — OCR is required for those."
        )
    return pages


def _sanitize(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\x00", "")
    cleaned = "".join(
        ch if (ch >= " " or ch in "\t\n\r") else " "
        for ch in text
    )
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
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        if end == len(words):
            break
        start += chunk_size - overlap
    return chunks