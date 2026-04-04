from __future__ import annotations

"""
ingest_to_chroma.py

Loads chunks from output/chunks/all_chunks.jsonl into a ChromaDB collection
using a local HuggingFace sentence-transformer embedding model.

This matches the ChromaDB + HuggingFace stack specified in your proposal.

Usage:
    python ingest_to_chroma.py [--chunks-file path] [--collection-name name]

Environment variables (optional):
    CHROMA_HOST      - ChromaDB host (default: localhost)
    CHROMA_PORT      - ChromaDB port (default: 8000)
    EMBED_MODEL      - HuggingFace model name (default: BAAI/bge-m3)
    COLLECTION_NAME  - ChromaDB collection name (default: ubs_knowledge_base)
"""

import argparse  # noqa: E402
import logging  # noqa: E402
import os  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

import chromadb  # noqa: E402
import jsonlines  # noqa: E402
from chromadb.utils import embedding_functions  # noqa: E402
from tqdm import tqdm  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("ingest")

# ── Config ────────────────────────────────────────────────────────────────────
CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
EMBED_MODEL = os.getenv("EMBED_MODEL", "BAAI/bge-m3")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "ubs_knowledge_base")
DEFAULT_CHUNKS_FILE = Path(__file__).parent / "output" / "chunks" / "all_chunks.jsonl"

# Batch size for upserts — ChromaDB handles large batches fine but stay conservative
BATCH_SIZE = 100


def build_embedding_fn(model_name: str) -> embedding_functions.SentenceTransformerEmbeddingFunction:
    """Return a ChromaDB-compatible SentenceTransformer embedding function."""
    logger.info(f"Loading embedding model: {model_name}")
    return embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=model_name,
        device="cpu",  # change to "cuda" if GPU available
        normalize_embeddings=True,
    )


def get_or_create_collection(
    client: chromadb.ClientAPI,
    name: str,
    embed_fn: embedding_functions.SentenceTransformerEmbeddingFunction,
) -> chromadb.Collection:
    """Get existing collection or create it with the given embedding function."""
    try:
        collection = client.get_collection(name=name, embedding_function=embed_fn)
        count = collection.count()
        logger.info(f"Found existing collection '{name}' with {count} documents")
    except Exception:
        collection = client.create_collection(
            name=name,
            embedding_function=embed_fn,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(f"Created new collection '{name}'")
    return collection


def load_chunks(chunks_file: Path) -> list[dict]:
    """Load all chunks from JSONL file."""
    chunks = []
    with jsonlines.open(chunks_file) as reader:
        for obj in reader:
            chunks.append(obj)
    logger.info(f"Loaded {len(chunks)} chunks from {chunks_file}")
    return chunks


def ingest(
    chunks_file: Path = DEFAULT_CHUNKS_FILE,
    collection_name: str = COLLECTION_NAME,
    embed_model: str = EMBED_MODEL,
    chroma_host: str = CHROMA_HOST,
    chroma_port: int = CHROMA_PORT,
    skip_existing: bool = True,
) -> int:
    """Ingest chunks into ChromaDB.

    Returns the total number of documents in the collection after ingestion.
    """
    if not chunks_file.exists():
        logger.error(f"Chunks file not found: {chunks_file}")
        logger.error("Run chunk_all.py first.")
        sys.exit(1)

    # Connect to ChromaDB
    try:
        client = chromadb.HttpClient(host=chroma_host, port=chroma_port)
        client.heartbeat()
        logger.info(f"Connected to ChromaDB at {chroma_host}:{chroma_port}")
    except Exception as e:
        logger.warning(f"Could not connect to remote ChromaDB ({e}), using local persistent client")
        client = chromadb.PersistentClient(path=str(Path(__file__).parent / "output" / "chroma_db"))

    embed_fn = build_embedding_fn(embed_model)
    collection = get_or_create_collection(client, collection_name, embed_fn)

    chunks = load_chunks(chunks_file)

    # Get existing IDs to support incremental updates
    existing_ids: set[str] = set()
    if skip_existing and collection.count() > 0:
        # Fetch all IDs in batches
        logger.info("Fetching existing IDs for deduplication...")
        results = collection.get(include=[])  # only IDs
        existing_ids = set(results["ids"])
        logger.info(f"  {len(existing_ids)} documents already in collection")

    # Filter to new chunks only
    new_chunks = [c for c in chunks if c["id"] not in existing_ids]
    skipped = len(chunks) - len(new_chunks)
    logger.info(f"Ingesting {len(new_chunks)} new chunks (skipping {skipped} existing)")

    if not new_chunks:
        logger.info("Nothing to ingest.")
        return collection.count()

    # Upsert in batches
    total_ingested = 0
    for i in tqdm(range(0, len(new_chunks), BATCH_SIZE), desc="Ingesting batches"):
        batch = new_chunks[i : i + BATCH_SIZE]
        collection.upsert(
            ids=[c["id"] for c in batch],
            documents=[c["text"] for c in batch],
            metadatas=[c["metadata"] for c in batch],
        )
        total_ingested += len(batch)

    final_count = collection.count()
    logger.info(
        f"Ingestion complete. Collection '{collection_name}' now has {final_count} documents."
    )
    return final_count


def query_test(
    collection_name: str = COLLECTION_NAME,
    embed_model: str = EMBED_MODEL,
) -> None:
    """Quick smoke test: run a sample query against the collection."""
    try:
        client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
        client.heartbeat()
    except Exception:
        client = chromadb.PersistentClient(path=str(Path(__file__).parent / "output" / "chroma_db"))

    embed_fn = build_embedding_fn(embed_model)
    collection = client.get_collection(name=collection_name, embedding_function=embed_fn)

    test_queries = [
        "How do I block my credit card?",
        "What documents do I need to open an account?",
        "How do I set up e-banking?",
    ]

    print("\n── Smoke Test Queries ──────────────────────────────────────")
    for q in test_queries:
        results = collection.query(
            query_texts=[q],
            n_results=2,
            include=["documents", "metadatas", "distances"],
        )
        print(f"\nQ: {q}")
        docs = results["documents"] or [[]]
        metas = results["metadatas"] or [[]]
        dists = results["distances"] or [[]]
        for doc, meta, dist in zip(
            docs[0],
            metas[0],
            dists[0],
            strict=False,
        ):
            print(f"  [{dist:.3f}] {meta['source_url']}")
            print(f"  {doc[:150]}...")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest UBS chunks into ChromaDB")
    parser.add_argument("--chunks-file", type=Path, default=DEFAULT_CHUNKS_FILE)
    parser.add_argument("--collection-name", default=COLLECTION_NAME)
    parser.add_argument("--embed-model", default=EMBED_MODEL)
    parser.add_argument("--no-skip-existing", action="store_true")
    parser.add_argument(
        "--test-query", action="store_true", help="Run smoke test queries after ingestion"
    )
    args = parser.parse_args()

    ingest(
        chunks_file=args.chunks_file,
        collection_name=args.collection_name,
        embed_model=args.embed_model,
        skip_existing=not args.no_skip_existing,
    )

    if args.test_query:
        query_test(collection_name=args.collection_name, embed_model=args.embed_model)
