"""Document ingestion pipeline for processing and indexing documents into PostgreSQL/pgvector.

Supports PDF and DOCX files from the docs/ directory. Uses a local
HuggingFace embedding model and cosine similarity search via pgvector.
"""

import os
import uuid

from sentence_transformers import SentenceTransformer
from sqlalchemy import create_engine, text

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
    text_content: str,
    chunk_size: int = pipeline_settings.chunk_size,
    chunk_overlap: int = pipeline_settings.chunk_overlap,
) -> list[str]:
    """Split text into overlapping chunks of approximately equal size.

    Args:
        text_content: The full text to split into chunks.
        chunk_size: The target number of characters per chunk.
        chunk_overlap: The number of overlapping characters between consecutive chunks.

    Returns:
        A list of text chunks.
    """
    chunks = []
    start = 0
    text_length = len(text_content)

    while start < text_length:
        end = start + chunk_size
        chunk = text_content[start:end]
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
                extracted_text = extract_text_from_pdf(file_path)
            elif file_extension == ".docx":
                extracted_text = extract_text_from_docx(file_path)
            else:
                continue

            if extracted_text.strip():
                documents.append({"filename": filename, "text": extracted_text})
                print(f"  Extracted {len(extracted_text)} characters")
            else:
                print("  Skipped (no text content)")
        except Exception as error:
            print(f"  Error processing {filename}: {error}")

    return documents


def run_ingestion(
    docs_directory: str = pipeline_settings.docs_directory,
    database_url: str = pipeline_settings.database_url,
    embedding_model_name: str = pipeline_settings.embedding_model_name,
    chunk_size: int = pipeline_settings.chunk_size,
    chunk_overlap: int = pipeline_settings.chunk_overlap,
) -> None:
    """Execute the full document ingestion pipeline.

    Loads documents from disk, chunks them, generates embeddings using a local
    HuggingFace model, and stores them in PostgreSQL via pgvector.

    Args:
        docs_directory: Path to the directory containing source documents.
        database_url: Sync PostgreSQL connection string.
        embedding_model_name: The HuggingFace model identifier for embeddings.
        chunk_size: The target character count per text chunk.
        chunk_overlap: The overlap in characters between consecutive chunks.
    """
    print("=" * 60)
    print("Document Ingestion Pipeline (pgvector)")
    print("=" * 60)
    print(f"Documents directory: {docs_directory}")
    print(f"Embedding model: {embedding_model_name}")
    print(f"Chunk size: {chunk_size}, Overlap: {chunk_overlap}")
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

    sync_database_url = database_url.replace("+asyncpg", "+psycopg2")
    print(f"\nConnecting to PostgreSQL: {sync_database_url}")
    db_engine = create_engine(sync_database_url)

    with db_engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

        # Clear existing documents
        connection.execute(text("DELETE FROM documents"))
        print("Cleared existing documents")

        # Insert in batches
        batch_size = 100
        for batch_start in range(0, len(all_chunks), batch_size):
            batch_end = min(batch_start + batch_size, len(all_chunks))
            for i in range(batch_start, batch_end):
                connection.execute(
                    text(
                        "INSERT INTO documents "
                        "(document_id, content, source, chunk_index, "
                        "total_chunks, metadata, embedding) "
                        "VALUES (:id, :content, :source, :chunk_index, "
                        ":total_chunks, :metadata, :embedding)"
                    ),
                    {
                        "id": str(uuid.uuid4()),
                        "content": all_chunks[i],
                        "source": all_metadata[i]["filename"],
                        "chunk_index": all_metadata[i]["chunk_index"],
                        "total_chunks": all_metadata[i]["total_chunks"],
                        "metadata": "{}",
                        "embedding": str(embeddings[i]),
                    },
                )
            print(f"  Indexed batch {batch_start}-{batch_end}")

    # Verify count
    with db_engine.connect() as connection:
        result = connection.execute(text("SELECT COUNT(*) FROM documents"))
        count = result.scalar()

    print(f"\nIngestion complete. {count} document chunks stored in PostgreSQL.")
    print("=" * 60)

    db_engine.dispose()


if __name__ == "__main__":
    run_ingestion()
