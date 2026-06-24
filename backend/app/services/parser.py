import fitz  # PyMuPDF
import docx
from pathlib import Path
from typing import List, Tuple
from app.core.config import settings


def extract_text_with_pages(file_path: str, file_type: str) -> List[Tuple[str, int]]:
    """
    Returns list of (text, page_number) tuples.
    TXT files return single entry with page 1.
    """
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
    doc = fitz.open(path)
    for i, page in enumerate(doc, start=1):
        text = page.get_text("text").strip()
        if text:
            pages.append((text, i))
    doc.close()
    return pages


def _extract_txt(path: str) -> List[Tuple[str, int]]:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read().strip()
    return [(content, 1)]


def _extract_docx(path: str) -> List[Tuple[str, int]]:
    doc = docx.Document(path)
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    full_text = "\n".join(paragraphs)
    return [(full_text, 1)]


def chunk_text(text: str, chunk_size: int, overlap: int) -> List[str]:
    """Split text into overlapping chunks by word count."""
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
