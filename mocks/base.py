"""Shared base for all mock MCP servers.

Provides the JSON-RPC request/response models and a factory to create
a FastAPI app from a set of tool definitions and handlers.
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field


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


def create_mock_mcp_app(
    title: str,
    tool_definitions: list[dict],
    tool_handlers: dict[str, Any],
) -> FastAPI:
    """Create a FastAPI application that serves as a mock MCP server.

    Args:
        title: The name of this mock MCP server.
        tool_definitions: MCP tool schema definitions this server exposes.
        tool_handlers: Mapping of tool name to handler function.

    Returns:
        A configured FastAPI application.
    """
    app = FastAPI(title=title, version="0.1.0")

    @app.post("/mcp")
    async def handle_mcp_request(request: JsonRpcRequest) -> JsonRpcResponse:
        """Handle incoming MCP JSON-RPC requests.

        Args:
            request: The JSON-RPC request envelope.

        Returns:
            A JSON-RPC response with the tool result or tool list.
        """
        if request.method == "tools/list":
            return JsonRpcResponse(
                result={"tools": tool_definitions},
                id=request.id,
            )

        if request.method == "tools/call":
            tool_name = request.params.get("name", "")
            arguments = request.params.get("arguments", {})

            handler = tool_handlers.get(tool_name)
            if handler is None:
                return JsonRpcResponse(
                    error={"code": -32601, "message": f"Unknown tool: {tool_name}"},
                    id=request.id,
                )

            result = handler(arguments)
            return JsonRpcResponse(result=result, id=request.id)

        return JsonRpcResponse(
            error={"code": -32601, "message": f"Unknown method: {request.method}"},
            id=request.id,
        )

    @app.get("/health")
    async def health_check() -> dict[str, str]:
        """Return mock MCP server health status."""
        return {
            "status": "healthy",
            "server": title,
            "timestamp": datetime.now(UTC).isoformat(),
        }

    return app
