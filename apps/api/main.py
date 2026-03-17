"""FastAPI application entry point for the customer service chatbot."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from apps.api.auth.routes import router as auth_router
from apps.api.chat.routes import router as chat_router
from apps.api.config import settings
from apps.api.database.connection import engine
from apps.api.database.models import Base
from apps.api.logging_config import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown lifecycle events.

    Creates database tables on startup and disposes the engine on shutdown.

    Args:
        application: The FastAPI application instance.

    Yields:
        Control back to the application during its active lifetime.
    """
    logger.info("application_startup")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    logger.info("database_tables_created")
    yield
    await engine.dispose()
    logger.info("application_shutdown")


app = FastAPI(
    title="Customer Service Chatbot API",
    description="AI-powered customer service chatbot with LangGraph agentic workflow",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api")
app.include_router(chat_router, prefix="/api")


@app.get("/api/health")
async def health_check() -> dict[str, str]:
    """Return the health status of the API service.

    Returns:
        A dictionary with status and LLM mode (mock or live).
    """
    return {
        "status": "healthy",
        "llm_mode": "mock" if settings.is_llm_mock_mode else "live",
    }


@app.get("/docs", include_in_schema=False)
async def scalar_docs() -> HTMLResponse:
    """Serve the Scalar API reference UI.

    Returns:
        An HTML page rendering the Scalar API documentation.
    """
    return HTMLResponse(
        content=f"""
<!DOCTYPE html>
<html>
<head>
    <title>{app.title} - API Reference</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
</head>
<body>
    <script
        id="api-reference"
        data-url="{app.openapi_url}"
        data-configuration='{{"theme": "kepler", "layout": "modern"}}'
    ></script>
    <script src="https://cdn.jsdelivr.net/npm/@scalar/api-reference"></script>
</body>
</html>
        """,
    )
