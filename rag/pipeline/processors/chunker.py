from __future__ import annotations

"""
processors/chunker.py

Splits a cleaned page document into RAG-ready chunks.

Strategy:
- Try to split on section boundaries first (preserves semantic units)
- If a section is too large, split on paragraph boundaries
- If a paragraph is still too large, split on sentence boundaries with overlap
- Each chunk carries full metadata for ChromaDB ingestion

Target: 350 tokens per chunk, max 500, overlap 50 tokens.
"""

import hashlib  # noqa: E402
import re  # noqa: E402
from datetime import UTC, datetime  # noqa: E402

import tiktoken  # noqa: E402

TARGET_TOKENS = 350
MAX_TOKENS = 500
OVERLAP_TOKENS = 50

# Use cl100k_base (GPT-4 / text-embedding-3) — close enough for sizing
_enc = tiktoken.get_encoding("cl100k_base")


def _count_tokens(text: str) -> int:
    return len(_enc.encode(text))


def _split_sentences(text: str) -> list[str]:
    """Naive sentence splitter — handles common cases well enough."""
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def _chunk_text(text: str, overlap_tokens: int = OVERLAP_TOKENS) -> list[str]:
    """Split text into chunks of ~TARGET_TOKENS each.

    Uses a sliding window with overlap so context isn't lost at boundaries.
    """
    sentences = _split_sentences(text)
    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0

    for sentence in sentences:
        s_tokens = _count_tokens(sentence)

        # If single sentence is bigger than max, hard-split it
        if s_tokens > MAX_TOKENS:
            if current:
                chunks.append(" ".join(current))
                current, current_tokens = [], 0
            # Hard split by token window
            encoded = _enc.encode(sentence)
            for i in range(0, len(encoded), TARGET_TOKENS - overlap_tokens):
                window = encoded[i : i + TARGET_TOKENS]
                chunks.append(_enc.decode(window))
            continue

        if current_tokens + s_tokens > MAX_TOKENS:
            chunks.append(" ".join(current))
            # Overlap: keep last N tokens worth of sentences
            overlap_sents: list[str] = []
            overlap_count = 0
            for s in reversed(current):
                t = _count_tokens(s)
                if overlap_count + t > overlap_tokens:
                    break
                overlap_sents.insert(0, s)
                overlap_count += t
            current = overlap_sents
            current_tokens = overlap_count

        current.append(sentence)
        current_tokens += s_tokens

    if current:
        chunks.append(" ".join(current))

    return [c for c in chunks if c.strip()]


def _make_chunk_id(url: str, chunk_index: int) -> str:
    """Deterministic ID: hash of URL + chunk index."""
    slug = re.sub(r"[^a-z0-9]+", "-", url.lower()).strip("-")
    # Keep slug short
    if len(slug) > 80:
        slug = slug[:80]
    return f"{slug}-chunk-{chunk_index}"


def chunk_document(doc: dict, doc_type: str = "help_faq") -> list[dict]:
    """Take a cleaned document dict and return a list of chunk dicts ready for ChromaDB ingestion.

    Each chunk:
    {
        "id": str,
        "text": str,
        "metadata": {
            "source_url": str,
            "title": str,
            "topic": str,
            "subtopic": str,
            "doc_type": str,
            "scraped_at": str (ISO8601),
            "chunk_index": int,
            "total_chunks": int,   # filled in after all chunks known
            "token_count": int,
        }
    }
    """
    url = doc["url"]
    scraped_at = datetime.now(UTC).isoformat()
    raw_chunks: list[str] = []

    # Try section-level chunking first
    for section in doc.get("sections", []):
        heading = section.get("heading", "")
        body = section.get("body", "")
        section_text = f"{heading}\n{body}" if heading else body
        section_tokens = _count_tokens(section_text)

        if section_tokens <= MAX_TOKENS:
            raw_chunks.append(section_text)
        else:
            # Section too big — split it, prepend heading to each sub-chunk
            sub_chunks = _chunk_text(body)
            for sc in sub_chunks:
                raw_chunks.append(f"{heading}\n{sc}" if heading else sc)

    # Fallback if no sections
    if not raw_chunks and doc.get("full_text"):
        raw_chunks = _chunk_text(doc["full_text"])

    # Remove duplicates while preserving order
    seen: set[str] = set()
    deduped: list[str] = []
    for c in raw_chunks:
        key = hashlib.md5(c.encode(), usedforsecurity=False).hexdigest()
        if key not in seen:
            seen.add(key)
            deduped.append(c)

    total = len(deduped)
    result: list[dict] = []

    for i, text in enumerate(deduped):
        result.append(
            {
                "id": _make_chunk_id(url, i),
                "text": text.strip(),
                "metadata": {
                    "source_url": url,
                    "title": doc.get("title", ""),
                    "topic": doc.get("topic", ""),
                    "subtopic": doc.get("subtopic", ""),
                    "doc_type": doc_type,
                    "scraped_at": scraped_at,
                    "chunk_index": i,
                    "total_chunks": total,
                    "token_count": _count_tokens(text),
                },
            }
        )

    return result
