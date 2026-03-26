from __future__ import annotations
"""
chunk_all.py

Orchestrates the chunking of all processed documents in output/processed/.
Saves all resulting chunks to output/chunks/all_chunks.jsonl.
"""

import json
import logging
import sys
from pathlib import Path
from collections import defaultdict

import jsonlines
from processors.chunker import chunk_document

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("chunk_all")

PROCESSED_DIR = Path(__file__).parent / "output" / "processed"
CHUNKS_DIR = Path(__file__).parent / "output" / "chunks"
ALL_CHUNKS_FILE = CHUNKS_DIR / "all_chunks.jsonl"


def run_chunker() -> dict[str, int]:
    """
    Process all files in output/processed/ and save chunks to all_chunks.jsonl.
    Returns a dictionary of counts per document type.
    """
    if not PROCESSED_DIR.exists():
        logger.error(f"Processed directory not found: {PROCESSED_DIR}")
        return {}

    CHUNKS_DIR.mkdir(parents=True, exist_ok=True)

    counts: dict[str, int] = defaultdict(int)
    all_chunks: list[dict] = []

    processed_files = list(PROCESSED_DIR.glob("*.json"))
    if not processed_files:
        logger.warning(f"No processed files found in {PROCESSED_DIR}")
        return {}

    logger.info(f"Chunking {len(processed_files)} documents...")

    for fpath in processed_files:
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                doc = json.load(f)
            
            # Use filename prefix or metadata to determine doc_type if possible
            # For now, we'll try to guess from the filename if metadata is missing
            doc_type = doc.get("doc_type", "unknown")
            if doc_type == "unknown":
                if "help" in fpath.name:
                    doc_type = "help_faq"
                elif "private" in fpath.name:
                    doc_type = "product_service"
                elif "wealth-management" in fpath.name:
                    doc_type = "wealth_management"
                elif fpath.name.startswith("pdf__"):
                    doc_type = "pdf_brochure"

            chunks = chunk_document(doc, doc_type=doc_type)
            all_chunks.extend(chunks)
            counts[doc_type] += len(chunks)
            
        except Exception as e:
            logger.error(f"Error processing {fpath.name}: {e}")

    # Write all chunks to JSONL
    logger.info(f"Writing {len(all_chunks)} chunks to {ALL_CHUNKS_FILE}")
    with jsonlines.open(ALL_CHUNKS_FILE, mode="w") as writer:
        writer.write_all(all_chunks)

    return dict(counts)


if __name__ == "__main__":
    result_counts = run_chunker()
    total_chunks = sum(result_counts.values())
    print(f"\nChunking complete: {total_chunks} documents processed.")
    for dtype, count in result_counts.items():
        print(f"  {dtype}: {count}")
