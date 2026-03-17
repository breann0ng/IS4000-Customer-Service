"""Mem0 memory manager with Redis backend for short-context memory."""

from mem0 import Memory

from apps.api.config import settings
from apps.api.logging_config import get_logger

logger = get_logger(__name__)


class MemoryManager:
    """Manages short-term conversational memory using mem0 with Redis storage.

    Uses a local HuggingFace sentence-transformers model for embeddings,
    avoiding any external API dependency for the memory subsystem.
    """

    def __init__(self) -> None:
        """Initialize the memory manager. Client is lazily created on first use."""
        self._client: Memory | None = None

    def _get_client(self) -> Memory:
        """Return the mem0 Memory client, creating it on first access.

        Returns:
            The configured mem0 Memory instance.
        """
        if self._client is None:
            config: dict = {
                "vector_store": {
                    "provider": "redis",
                    "config": {
                        "redis_url": settings.redis_url,
                        "collection_name": "chatbot_memory",
                    },
                },
                "embedder": {
                    "provider": "huggingface",
                    "config": {
                        "model": settings.embedding_model_name,
                        "model_kwargs": {"device": "cpu"},
                    },
                },
            }

            if settings.gemini_api_key and settings.gemini_api_key != "your-gemini-api-key-here":
                config["llm"] = {
                    "provider": "gemini",
                    "config": {
                        "api_key": settings.gemini_api_key,
                        "model": settings.gemini_model,
                    },
                }

            self._client = Memory.from_config(config)
            logger.info(
                "mem0_client_initialized",
                embedder="huggingface",
                model=settings.embedding_model_name,
            )
        return self._client

    async def store_memory(
        self,
        user_id: str,
        messages: list[dict[str, str]],
    ) -> None:
        """Store conversation messages in mem0 for future context retrieval.

        Args:
            user_id: The unique identifier of the user.
            messages: A list of message dicts with 'role' and 'content' keys.
        """
        try:
            client = self._get_client()
            client.add(messages=messages, user_id=user_id)
            logger.info("memory_stored", user_id=user_id, message_count=len(messages))
        except Exception:
            logger.exception("memory_store_failed", user_id=user_id)

    async def retrieve_memory(
        self,
        user_id: str,
        query: str,
    ) -> list[dict]:
        """Retrieve relevant memories for the given user and query.

        Args:
            user_id: The unique identifier of the user.
            query: The search query to find relevant memories.

        Returns:
            A list of memory result dictionaries from mem0.
        """
        try:
            client = self._get_client()
            results = client.search(query=query, user_id=user_id, limit=10)
            logger.info("memory_retrieved", user_id=user_id, result_count=len(results))
            return results
        except Exception:
            logger.exception("memory_retrieve_failed", user_id=user_id)
            return []


memory_manager = MemoryManager()
