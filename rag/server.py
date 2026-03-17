"""RAG MCP server that queries ChromaDB for relevant document chunks.

Exposes a retrieve_documents tool over Streamable HTTP (JSON-RPC)
that performs cosine similarity search against the local vector store.

Run standalone:
    uv run uvicorn rag.server:app --host 0.0.0.0 --port 9004
"""

import os

import chromadb
from chromadb.config import Settings as ChromaSettings
from fastapi import FastAPI
from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer

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
_chroma_collection: chromadb.Collection | None = None


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


def _get_chroma_collection() -> chromadb.Collection | None:
    """Open the ChromaDB collection for querying.

    Returns:
        The ChromaDB collection, or None if the vector store does not exist.
    """
    global _chroma_collection
    if _chroma_collection is not None:
        return _chroma_collection

    persist_directory = pipeline_settings.chroma_persist_directory
    if not os.path.isdir(persist_directory):
        return None

    chroma_client = chromadb.PersistentClient(
        path=persist_directory,
        settings=ChromaSettings(anonymized_telemetry=False),
    )

    existing_collections = [collection.name for collection in chroma_client.list_collections()]
    if pipeline_settings.chroma_collection_name not in existing_collections:
        return None

    _chroma_collection = chroma_client.get_collection(
        name=pipeline_settings.chroma_collection_name,
    )
    return _chroma_collection


def retrieve_documents(query: str, top_k: int) -> dict:
    """Query ChromaDB for the top-k most similar document chunks.

    Args:
        query: The search query text.
        top_k: The number of chunks to retrieve.

    Returns:
        A dictionary with a 'chunks' list of matching documents and metadata.
    """
    collection = _get_chroma_collection()
    if collection is None:
        return {
            "chunks": [],
            "error": "Vector store not found. Run 'poe ingest' to index documents first.",
        }

    embedding_model = _get_embedding_model()
    query_embedding = embedding_model.encode([query]).tolist()

    results = collection.query(
        query_embeddings=query_embedding,
        n_results=min(top_k, collection.count()) if collection.count() > 0 else 0,
        include=["documents", "metadatas", "distances"],
    )

    chunks = []
    raw_documents = results.get("documents") or [[]]
    raw_metadatas = results.get("metadatas") or [[]]
    raw_distances = results.get("distances") or [[]]
    documents = raw_documents[0]
    metadatas = raw_metadatas[0]
    distances = raw_distances[0]

    for document, metadata, distance in zip(documents, metadatas, distances, strict=True):
        similarity_score = 1.0 - distance
        chunks.append(
            {
                "text": document,
                "metadata": metadata,
                "score": round(similarity_score, 4),
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
    collection = _get_chroma_collection()
    document_count = collection.count() if collection else 0
    return {
        "status": "healthy",
        "server": "rag-mcp",
        "document_count": document_count,
    }
