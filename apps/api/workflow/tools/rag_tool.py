"""Custom MCP server client for RAG retrieval from the local vector store."""

from apps.api.config import settings
from apps.api.logging_config import get_logger
from apps.api.workflow.tools.mcp_client import McpClient

logger = get_logger(__name__)

rag_mcp_client = McpClient(server_url=settings.mcp_rag_server_url)


async def retrieve_rag_chunks(
    query: str,
    top_k: int | None = None,
) -> list[dict[str, str]]:
    """Retrieve the top-k most relevant document chunks from the RAG MCP server.

    Calls the RAG MCP server which performs cosine similarity search against
    the local ChromaDB vector store and returns matching chunks.

    Args:
        query: The search query to find relevant document chunks.
        top_k: The number of chunks to retrieve. Defaults to the configured value.

    Returns:
        A list of dictionaries containing chunk text and metadata.
    """
    effective_top_k = top_k if top_k is not None else settings.rag_top_k

    logger.info("rag_retrieval_start", query_length=len(query), top_k=effective_top_k)

    result = await rag_mcp_client.call_tool(
        tool_name="retrieve_documents",
        arguments={
            "query": query,
            "top_k": effective_top_k,
        },
    )

    if "error" in result:
        logger.error("rag_retrieval_failed", error=result["error"])
        return []

    chunks = result.get("chunks", [])
    logger.info("rag_retrieval_complete", chunk_count=len(chunks))
    return chunks
