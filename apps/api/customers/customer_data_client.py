"""Unified customer data access client.

Provides a single async entry point for customer context retrieval,
backed by either MCP (production-like mode) or direct SQLite reads
(local fallback mode).
"""

from __future__ import annotations

from typing import Any

from apps.api.config import settings
from apps.api.customers.sqlite_repository import repository
from apps.api.logging_config import get_logger
from apps.api.workflow.tools.mcp_client import McpClient

logger = get_logger(__name__)

customer_data_mcp_client = McpClient(server_url=settings.mcp_customer_data_url)


def _normalize_mcp_bundle(result: dict[str, Any]) -> dict[str, Any]:
    """Normalize MCP tool output into the app's customer bundle shape."""
    return {
        "profile": result.get("profile") or result.get("customer") or {},
        "accounts": result.get("accounts") or [],
        "cards": result.get("cards") or [],
        "portfolio": result.get("portfolio_detail") or result.get("portfolio") or {},
        "credit": result.get("credit") or {},
        "real_estate": result.get("real_estate") or [],
        "goals": result.get("goals") or [],
        "cashflow": result.get("cashflow") or {},
        "system_triggers": result.get("system_triggers") or [],
        "insights_signals": result.get("insights_signals") or result.get("insights") or [],
        "transactions": result.get("transactions") or [],
        "applications": result.get("applications") or [],
        "appointments": result.get("appointments") or [],
        "kyc": result.get("kyc") or {},
        "mortgages": result.get("mortgages") or [],
    }


async def get_customer_bundle(customer_id: str, transaction_limit: int = 10) -> dict[str, Any]:
    """Fetch customer context via MCP by default, or direct SQLite when configured."""
    mode = settings.customer_data_access_mode.lower().strip()

    if mode == "direct":
        return repository.build_customer_bundle(customer_id, transaction_limit=transaction_limit)

    result = await customer_data_mcp_client.call_tool(
        tool_name="customer_get_360",
        arguments={"customer_id": customer_id, "transaction_limit": transaction_limit},
    )

    if "error" in result:
        logger.error(
            "customer_data_mcp_fetch_failed",
            customer_id=customer_id,
            error=result["error"],
        )
        return {}

    return _normalize_mcp_bundle(result)
