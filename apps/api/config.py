"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Central configuration for the customer service chatbot backend."""

    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.1-flash-lite-preview"
    tavily_api_key: str = ""
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/chatbot"

    redis_url: str = "redis://localhost:6379/0"

    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"

    jwt_secret_key: str = "change-me-to-a-secure-random-string"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 60

    log_level: str = "INFO"

    mcp_banking_ops_url: str = "http://localhost:9001/mcp"
    mcp_knowledge_url: str = "http://localhost:9002/mcp"
    mcp_service_workflow_url: str = "http://localhost:9003/mcp"
    mcp_rag_server_url: str = "http://localhost:9004/mcp"

    langsmith_api_key: str = ""
    langsmith_project: str = "ubs-chatbot"

    rag_top_k: int = 5

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def is_llm_mock_mode(self) -> bool:
        """Check if the LLM is running in mock mode (no valid API key)."""
        key = self.gemini_api_key.lower()
        return not key or "your" in key or "gemini" in key or "api-key" in key


settings = Settings()
