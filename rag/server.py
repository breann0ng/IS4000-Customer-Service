"""RAG MCP server that queries PostgreSQL/pgvector for relevant document chunks.

Exposes a retrieve_documents tool over Streamable HTTP (JSON-RPC)
that performs cosine similarity search against the pgvector store.

Run standalone:
    uv run uvicorn rag.server:app --host 0.0.0.0 --port 9004
"""

import os

from fastapi import FastAPI
from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer
from sqlalchemy import create_engine, text

from rag.config import pipeline_settings

app = FastAPI(title="RAG MCP Server", version="0.1.0")


class JsonRpcRequest(BaseModel):
    """JSON-RPC 2.0 request envelope."""

    jsonrpc: str = "2.0"
    method: str
    params: dict = Field(default_factory=dict)
    id: int | str = 1


class JsonRpcResponse(BaseModel):
    """JSON-RPC 2.0 response envelope."""

    jsonrpc: str = "2.0"
    result: dict | list | None = None
    error: dict | None = None
    id: int | str = 1


TOOL_DEFINITIONS = [
    {
        "name": "retrieve_documents",
        "description": "Retrieve relevant document chunks via cosine similarity search",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query"},
                "top_k": {
                    "type": "integer",
                    "description": "Number of top chunks to return",
                },
            },
            "required": ["query"],
        },
    },
]

_embedding_model: SentenceTransformer | None = None
_db_engine = None


def _get_embedding_model() -> SentenceTransformer:
    """Load the embedding model from the local cache or download it.

    Returns:
        The loaded SentenceTransformer model.
    """
    global _embedding_model
    if _embedding_model is not None:
        return _embedding_model

    models_directory = pipeline_settings.models_directory
    model_slug = pipeline_settings.embedding_model_name.replace("/", "--")
    local_model_path = os.path.join(models_directory, model_slug)

    if os.path.isdir(local_model_path):
        _embedding_model = SentenceTransformer(local_model_path)
    else:
        os.makedirs(models_directory, exist_ok=True)
        _embedding_model = SentenceTransformer(pipeline_settings.embedding_model_name)
        _embedding_model.save(local_model_path)

    return _embedding_model


def _get_db_engine():  # noqa: ANN202
    """Return or create the sync SQLAlchemy engine for pgvector queries."""
    global _db_engine
    if _db_engine is None:
        _db_engine = create_engine(pipeline_settings.database_url)
    return _db_engine


def retrieve_documents(query: str, top_k: int) -> dict:
    """Query PostgreSQL/pgvector for the top-k most similar document chunks.

    Args:
        query: The search query text.
        top_k: The number of chunks to retrieve.

    Returns:
        A dictionary with a 'chunks' list of matching documents and metadata.
    """
    engine = _get_db_engine()

    try:
        # Check if documents table exists and has rows
        with engine.connect() as connection:
            result = connection.execute(
                text(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                    "WHERE table_name = 'documents')"
                )
            )
            if not result.scalar():
                return {
                    "chunks": [],
                    "error": (
                        "Documents table not found. "
                        "Run 'poe rag-ingestion' to index documents first."
                    ),
                }

            count_result = connection.execute(text("SELECT COUNT(*) FROM documents"))
            doc_count = count_result.scalar()
            if doc_count == 0:
                return {
                    "chunks": [],
                    "error": "No documents indexed. Run 'poe rag-ingestion' first.",
                }
    except Exception:
        return {
            "chunks": [],
            "error": "Database connection failed.",
        }

    embedding_model = _get_embedding_model()
    query_embedding = embedding_model.encode([query]).tolist()[0]

    chunks = []
    with engine.connect() as connection:
        results = connection.execute(
            text(
                "SELECT content, source, chunk_index, metadata, "
                "1 - (embedding <=> :embedding) AS similarity "
                "FROM documents "
                "ORDER BY embedding <=> :embedding "
                "LIMIT :top_k"
            ),
            {"embedding": str(query_embedding), "top_k": top_k},
        )

        for row in results:
            chunks.append(
                {
                    "text": row.content,
                    "metadata": {
                        "source": row.source,
                        "chunk_index": row.chunk_index,
                        **(row.metadata if row.metadata else {}),
                    },
                    "score": round(float(row.similarity), 4),
                }
            )

    return {"chunks": chunks}


@app.post("/mcp")
async def handle_mcp_request(request: JsonRpcRequest) -> JsonRpcResponse:
    """Handle incoming MCP JSON-RPC requests.

    Supports tools/call (retrieve_documents) and tools/list methods.

    Args:
        request: The JSON-RPC request envelope.

    Returns:
        A JSON-RPC response with the tool result or tool list.
    """
    if request.method == "tools/list":
        return JsonRpcResponse(
            result={"tools": TOOL_DEFINITIONS},
            id=request.id,
        )

    if request.method == "tools/call":
        tool_name = request.params.get("name", "")
        arguments = request.params.get("arguments", {})

        if tool_name != "retrieve_documents":
            return JsonRpcResponse(
                error={"code": -32601, "message": f"Unknown tool: {tool_name}"},
                id=request.id,
            )

        query = arguments.get("query", "")
        top_k = arguments.get("top_k", pipeline_settings.top_k)
        result = retrieve_documents(query=query, top_k=top_k)
        return JsonRpcResponse(result=result, id=request.id)

    return JsonRpcResponse(
        error={"code": -32601, "message": f"Unknown method: {request.method}"},
        id=request.id,
    )


@app.get("/health")
async def health_check() -> dict[str, str | int]:
    """Return RAG server health and collection status.

    Returns:
        A dictionary with server status and document count.
    """
    engine = _get_db_engine()
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT COUNT(*) FROM documents"))
            document_count = result.scalar()
    except Exception:
        document_count = 0

    return {
        "status": "healthy",
        "server": "rag-mcp-pgvector",
        "document_count": document_count,
    }
