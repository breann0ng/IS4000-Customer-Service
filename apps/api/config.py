"""Application configuration loaded from environment variables."""

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Central configuration for the customer service chatbot backend."""

    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"
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

    # mem0: short-context memory (Redis + local HF embeddings). LLM slot is Ollama only, never Gemini/OpenAI.
    mem0_infer: bool = Field(
        default=False,
        description="False: embed raw messages on add (no LLM). True: Ollama runs mem0 fact extraction.",
    )
    mem0_ollama_base_url: str = "http://127.0.0.1:11434"
    mem0_ollama_model: str = "llama3.2"

    # LLM Resiliency
    force_llm_mock_mode: bool = False
    llm_max_retries: int = 3
    llm_retry_min_wait: int = 1  # seconds
    llm_retry_max_wait: int = 10 # seconds
    llm_circuit_breaker_threshold: int = 5
    llm_circuit_breaker_cooldown: int = 60 # seconds
    local_llm_url: str = "" # e.g. http://localhost:11434/v1

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    @property
    def is_llm_mock_mode(self) -> bool:
        """Check if the LLM is running in mock mode (no valid API key)."""
        if self.force_llm_mock_mode:
            return True
        key = self.gemini_api_key.lower()
        if not key or any(p in key for p in ["your", "gemini", "api-key", "placeholder", "quota"]):
            return True
        return False


settings = Settings()


class ResiliencyManager:
    """Manages LLM API health and circuit breaker state."""

    _instance = None
    _failure_count = 0
    _last_failure_time = 0
    _is_tripped = False

    def __new__(cls) -> "ResiliencyManager":
        if cls._instance is None:
            cls._instance = super(ResiliencyManager, cls).__new__(cls)
        return cls._instance

    def record_failure(self, error: str | None = None) -> None:
        """Increment failure count and trip circuit breaker if threshold met.

        Certain upstream failures (notably Gemini quota exhaustion / 429) should
        trip the circuit breaker immediately to force fallbacks and avoid
        repeated failures across planner/synthesizer and MCP servers.
        """
        import time
        self._failure_count += 1
        self._last_failure_time = time.time()

        if error:
            normalized = error.lower()
            hard_quota_markers = [
                "resource_exhausted",
                "quota exceeded",
                "rate limit",
                "429",
                "too many requests",
                "generate_content_free_tier_requests",
                "generatecontentinputtokens",
                "generativelanguage.googleapis.com",
            ]
            if any(marker in normalized for marker in hard_quota_markers):
                # Immediately force mock/fallback paths for a cooldown period.
                self._is_tripped = True
                self._failure_count = settings.llm_circuit_breaker_threshold
                return

        if self._failure_count >= settings.llm_circuit_breaker_threshold:
            self._is_tripped = True

    def record_success(self) -> None:
        """Reset failure count and circuit breaker on success."""
        self._failure_count = 0
        self._is_tripped = False

    @property
    def is_circuit_breaker_tripped(self) -> bool:
        """Check if the circuit breaker is currently active."""
        import time
        if self._is_tripped:
            # Check if cooldown period has passed
            if time.time() - self._last_failure_time > settings.llm_circuit_breaker_cooldown:
                self._is_tripped = False
                self._failure_count = 0
                return False
            return True
        return False


resiliency_manager = ResiliencyManager()
