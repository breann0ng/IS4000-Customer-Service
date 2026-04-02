"""Shared base for all mock MCP servers.

Provides the JSON-RPC request/response models and a factory to create
a FastAPI app from a set of tool definitions and handlers.
"""

import sqlite3
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI
from pydantic import BaseModel, Field

# Shared database path
DB_PATH = Path("data/persona.db").absolute()

def get_persona_data(username: str) -> Optional[dict]:
    """Fetch all persona data from the SQLite database."""
    if not DB_PATH.exists():
        return None
        
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 1. Profile
        cursor.execute("SELECT * FROM profiles WHERE username = ?", (username,))
        profile_row = cursor.fetchone()
        if not profile_row:
            # Try by customer_id if username doesn't match
            cursor.execute("SELECT * FROM profiles WHERE customer_id = ?", (username,))
            profile_row = cursor.fetchone()
            if not profile_row:
                conn.close()
                return None
            
        profile = dict(profile_row)
        customer_id = profile["customer_id"]
        data = {"username": profile["username"], "profile": profile}
        
        # 2. Accounts
        cursor.execute("SELECT * FROM accounts WHERE customer_id = ?", (customer_id,))
        data["accounts"] = [dict(row) for row in cursor.fetchall()]
        
        # 3. Portfolio
        cursor.execute("SELECT * FROM portfolios WHERE customer_id = ?", (customer_id,))
        port = cursor.fetchone()
        data["portfolio"] = dict(port) if port else {}
        
        # 4. Credit
        cursor.execute("SELECT * FROM credit WHERE customer_id = ?", (customer_id,))
        credit = cursor.fetchone()
        data["credit"] = dict(credit) if credit else {}
        
        # 5. Credit Cards
        cursor.execute("SELECT * FROM credit_cards WHERE customer_id = ?", (customer_id,))
        data["credit_cards"] = [dict(row) for row in cursor.fetchall()]

        # 6. Real Estate
        cursor.execute("SELECT * FROM real_estate WHERE customer_id = ?", (customer_id,))
        data["real_estate"] = [dict(row) for row in cursor.fetchall()]

        # 7. Performance History
        cursor.execute("SELECT * FROM performance_history WHERE customer_id = ?", (customer_id,))
        data["performance_history"] = [dict(row) for row in cursor.fetchall()]
        
        # 8. Transactions
        cursor.execute("SELECT * FROM transactions WHERE customer_id = ?", (customer_id,))
        data["recent_transactions"] = [dict(row) for row in cursor.fetchall()]

        # 9. Appointments
        cursor.execute("SELECT * FROM appointments WHERE customer_id = ?", (customer_id,))
        data["appointments"] = [dict(row) for row in cursor.fetchall()]

        # 10. Notifications
        cursor.execute("SELECT * FROM notifications WHERE customer_id = ?", (customer_id,))
        data["notifications"] = [dict(row) for row in cursor.fetchall()]

        # 11. Applications
        cursor.execute("SELECT * FROM applications WHERE customer_id = ?", (customer_id,))
        data["applications"] = [dict(row) for row in cursor.fetchall()]

        conn.close()
        return data
    except Exception as e:
        print(f"Database error in get_persona_data: {e}")
        return None


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

            import inspect

            if inspect.iscoroutinefunction(handler):
                result = await handler(arguments)
            else:
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
