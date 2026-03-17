"""Document ingestion pipeline for processing and indexing documents into ChromaDB.

Supports PDF and DOCX files from the docs/ directory. Uses a local
HuggingFace embedding model and cosine similarity search.
"""

import os
import uuid

import chromadb
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer

from rag.config import pipeline_settings


def extract_text_from_pdf(file_path: str) -> str:
    """Extract all text content from a PDF file using PyMuPDF.

    Args:
        file_path: The absolute or relative path to the PDF file.

    Returns:
        The concatenated text from all pages of the PDF.
    """
    import pymupdf

    document = pymupdf.open(file_path)
    pages = [page.get_text() for page in document]
    document.close()
    return "\n".join(pages)


def extract_text_from_docx(file_path: str) -> str:
    """Extract all text content from a DOCX file.

    Args:
        file_path: The absolute or relative path to the DOCX file.

    Returns:
        The concatenated text from all paragraphs in the document.
    """
    from docx import Document

    document = Document(file_path)
    paragraphs = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
    return "\n".join(paragraphs)


def chunk_text(
    text: str,
    chunk_size: int = pipeline_settings.chunk_size,
    chunk_overlap: int = pipeline_settings.chunk_overlap,
) -> list[str]:
    """Split text into overlapping chunks of approximately equal size.

    Args:
        text: The full text to split into chunks.
        chunk_size: The target number of characters per chunk.
        chunk_overlap: The number of overlapping characters between consecutive chunks.

    Returns:
        A list of text chunks.
    """
    chunks = []
    start = 0
    text_length = len(text)

    while start < text_length:
        end = start + chunk_size
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk.strip())
        start = end - chunk_overlap

    return chunks


def load_documents(docs_directory: str) -> list[dict[str, str]]:
    """Load and extract text from all supported documents in the directory.

    Processes all PDF and DOCX files found in the specified directory.

    Args:
        docs_directory: Path to the directory containing documents.

    Returns:
        A list of dictionaries with 'filename' and 'text' keys.
    """
    documents = []
    supported_extensions = {".pdf", ".docx"}

    if not os.path.isdir(docs_directory):
        print(f"Documents directory not found: {docs_directory}")
        return documents

    for filename in sorted(os.listdir(docs_directory)):
        file_extension = os.path.splitext(filename)[1].lower()
        if file_extension not in supported_extensions:
            continue

        file_path = os.path.join(docs_directory, filename)
        print(f"Processing: {filename}")

        try:
            if file_extension == ".pdf":
                text = extract_text_from_pdf(file_path)
            elif file_extension == ".docx":
                text = extract_text_from_docx(file_path)
            else:
                continue

            if text.strip():
                documents.append({"filename": filename, "text": text})
                print(f"  Extracted {len(text)} characters")
            else:
                print("  Skipped (no text content)")
        except Exception as error:
            print(f"  Error processing {filename}: {error}")

    return documents


def run_ingestion(
    docs_directory: str = pipeline_settings.docs_directory,
    chroma_persist_directory: str = pipeline_settings.chroma_persist_directory,
    collection_name: str = pipeline_settings.chroma_collection_name,
    embedding_model_name: str = pipeline_settings.embedding_model_name,
    chunk_size: int = pipeline_settings.chunk_size,
    chunk_overlap: int = pipeline_settings.chunk_overlap,
    top_k: int = pipeline_settings.top_k,
) -> None:
    """Execute the full document ingestion pipeline.

    Loads documents from disk, chunks them, generates embeddings using a local
    HuggingFace model, and stores them in ChromaDB with cosine similarity.

    Args:
        docs_directory: Path to the directory containing source documents.
        chroma_persist_directory: Path where ChromaDB persists its data.
        collection_name: The ChromaDB collection name to store embeddings in.
        embedding_model_name: The HuggingFace model identifier for embeddings.
        chunk_size: The target character count per text chunk.
        chunk_overlap: The overlap in characters between consecutive chunks.
        top_k: The default number of results for similarity search (stored as metadata).
    """
    print("=" * 60)
    print("Document Ingestion Pipeline")
    print("=" * 60)
    print(f"Documents directory: {docs_directory}")
    print(f"Embedding model: {embedding_model_name}")
    print(f"Chunk size: {chunk_size}, Overlap: {chunk_overlap}")
    print(f"Default top_k: {top_k}")
    print()

    documents = load_documents(docs_directory)
    if not documents:
        print("No documents found to process.")
        return

    print(f"\nLoaded {len(documents)} document(s)")

    all_chunks = []
    all_metadata = []
    for document in documents:
        chunks = chunk_text(document["text"], chunk_size, chunk_overlap)
        for chunk_index, chunk in enumerate(chunks):
            all_chunks.append(chunk)
            all_metadata.append(
                {
                    "filename": document["filename"],
                    "chunk_index": chunk_index,
                    "total_chunks": len(chunks),
                }
            )

    print(f"Generated {len(all_chunks)} chunk(s)")

    if not all_chunks:
        print("No chunks generated. Exiting.")
        return

    models_directory = pipeline_settings.models_directory
    model_slug = embedding_model_name.replace("/", "--")
    local_model_path = os.path.join(models_directory, model_slug)

    if os.path.isdir(local_model_path):
        print(f"\nLoading embedding model from local cache: {local_model_path}")
        embedding_model = SentenceTransformer(local_model_path)
    else:
        print(f"\nModel not found locally. Downloading: {embedding_model_name}")
        os.makedirs(models_directory, exist_ok=True)
        embedding_model = SentenceTransformer(embedding_model_name)
        embedding_model.save(local_model_path)
        print(f"  Saved model to: {local_model_path}")

    embeddings = embedding_model.encode(all_chunks, show_progress_bar=True).tolist()
    print(f"Generated {len(embeddings)} embedding(s)")

    print(f"\nInitializing ChromaDB at: {chroma_persist_directory}")
    os.makedirs(chroma_persist_directory, exist_ok=True)
    chroma_client = chromadb.PersistentClient(
        path=chroma_persist_directory,
        settings=ChromaSettings(anonymized_telemetry=False),
    )

    existing_collections = [collection.name for collection in chroma_client.list_collections()]
    if collection_name in existing_collections:
        chroma_client.delete_collection(collection_name)
        print(f"Deleted existing collection: {collection_name}")

    collection = chroma_client.create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )

    chunk_ids = [str(uuid.uuid4()) for _ in all_chunks]

    batch_size = 100
    for batch_start in range(0, len(all_chunks), batch_size):
        batch_end = min(batch_start + batch_size, len(all_chunks))
        collection.add(
            ids=chunk_ids[batch_start:batch_end],
            documents=all_chunks[batch_start:batch_end],
            embeddings=embeddings[batch_start:batch_end],
            metadatas=all_metadata[batch_start:batch_end],
        )
        print(f"  Indexed batch {batch_start}-{batch_end}")

    print(
        f"\nIngestion complete. Collection '{collection_name}' has {collection.count()} documents."
    )
    print("=" * 60)


if __name__ == "__main__":
    run_ingestion()
