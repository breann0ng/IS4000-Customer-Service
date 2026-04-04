"""Customer data MCP server backed by SQLite.

This server exposes read-only tools for the chatbot and API routes to
retrieve customer context from the shared customer_data.db database.
"""

from __future__ import annotations

from typing import Any

from apps.api.customers.sqlite_repository import repository
from mcp_servers.base import create_mock_mcp_app

TOOL_DEFINITIONS = [
    {
        "name": "customer_get_360",
        "description": (
            "Return a full customer context bundle including profile, accounts, "
            "portfolio, lending, and compliance data."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "transaction_limit": {"type": "integer", "default": 10},
            },
            "required": ["customer_id"],
        },
    },
    {
        "name": "customer_get_summary",
        "description": "Return a compact profile and account summary for a customer.",
        "inputSchema": {
            "type": "object",
            "properties": {"customer_id": {"type": "string"}},
            "required": ["customer_id"],
        },
    },
    {
        "name": "customer_get_transactions",
        "description": "Return recent transactions for a customer, optionally filtered by account.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "account_id": {"type": "string"},
                "limit": {"type": "integer", "default": 10},
            },
            "required": ["customer_id"],
        },
    },
    {
        "name": "customer_get_profile",
        "description": "Return the customer profile row from SQLite.",
        "inputSchema": {
            "type": "object",
            "properties": {"customer_id": {"type": "string"}},
            "required": ["customer_id"],
        },
    },
]


def _not_found(customer_id: str) -> dict[str, Any]:
    return {"error": f"Customer not found: {customer_id}"}


def _build_mcp_portfolio(bundle: dict[str, Any]) -> dict[str, Any]:
    portfolio = bundle.get("portfolio") or {}
    allocation_snapshot = portfolio.get("allocation_snapshot") or {}
    return {
        "allocation": allocation_snapshot,
        "summary": portfolio.get("summary") or {},
        "last_updated": portfolio.get("last_updated"),
        "benchmark": portfolio.get("benchmark"),
    }


def _build_mcp_lending(bundle: dict[str, Any]) -> dict[str, Any]:
    credit = bundle.get("credit") or {}
    facilities = repository.get_credit_facilities(bundle.get("profile", {}).get("customer_id", ""))
    return {
        "summary": {
            "total_limit_usd": sum(float(f.get("principal_usd") or 0) for f in facilities),
            "total_drawn_usd": sum(float(f.get("drawn_amount_usd") or 0) for f in facilities),
            "total_available_usd": sum(
                float(f.get("available_amount_usd") or 0) for f in facilities
            ),
            "total_card_limit_usd": sum(
                float(card.get("credit_limit_usd") or 0) for card in bundle.get("cards", [])
            ),
            "total_card_outstanding_usd": sum(
                float(card.get("outstanding_balance_usd") or 0) for card in bundle.get("cards", [])
            ),
        },
        "facilities": facilities,
        "cards": bundle.get("cards") or credit.get("credit_cards") or [],
    }


def _customer_get_360(params: dict[str, Any]) -> dict[str, Any]:
    customer_id = str(params.get("customer_id", "")).strip()
    transaction_limit = int(params.get("transaction_limit") or 10)
    bundle = repository.build_customer_bundle(customer_id, transaction_limit=transaction_limit)
    if not bundle:
        return _not_found(customer_id)

    profile = bundle.get("profile") or {}
    accounts = bundle.get("accounts") or []
    portfolio = _build_mcp_portfolio(bundle)
    lending = _build_mcp_lending(bundle)

    return {
        "customer": profile,
        "profile": profile,
        "accounts": accounts,
        "portfolio": portfolio,
        "portfolio_detail": bundle.get("portfolio") or {},
        "cards": bundle.get("cards") or [],
        "credit": bundle.get("credit") or {},
        "real_estate": bundle.get("real_estate") or [],
        "goals": bundle.get("goals") or [],
        "cashflow": bundle.get("cashflow") or {},
        "lending": lending,
        "transactions": bundle.get("transactions") or [],
        "applications": bundle.get("applications") or [],
        "appointments": bundle.get("appointments") or [],
        "kyc": bundle.get("kyc") or {},
        "insights": bundle.get("insights_signals") or [],
        "insights_signals": bundle.get("insights_signals") or [],
        "system_triggers": bundle.get("system_triggers") or [],
        "mortgages": bundle.get("mortgages") or [],
    }


def _customer_get_summary(params: dict[str, Any]) -> dict[str, Any]:
    customer_id = str(params.get("customer_id", "")).strip()
    bundle = repository.build_customer_bundle(customer_id)
    if not bundle:
        return _not_found(customer_id)

    profile = bundle.get("profile") or {}
    portfolio = bundle.get("portfolio") or {}
    return {
        "profile": profile,
        "accounts": bundle.get("accounts") or [],
        "portfolio_summary": {
            "total_value": portfolio.get("total_value_usd"),
            "currency": portfolio.get("currency"),
            "ytd_return": portfolio.get("ytd_return_pct"),
        },
    }


def _customer_get_transactions(params: dict[str, Any]) -> dict[str, Any]:
    customer_id = str(params.get("customer_id", "")).strip()
    limit = int(params.get("limit") or 10)
    account_id = params.get("account_id")
    transactions = repository.get_transactions(customer_id, limit=limit, account_id=account_id)
    if not transactions and not repository.get_customer(customer_id):
        return _not_found(customer_id)
    return {"transactions": transactions}


def _customer_get_profile(params: dict[str, Any]) -> dict[str, Any]:
    customer_id = str(params.get("customer_id", "")).strip()
    profile = repository.get_customer(customer_id)
    if not profile:
        return _not_found(customer_id)
    return {"profile": profile}


app = create_mock_mcp_app(
    title="Customer Data MCP (9005)",
    tool_definitions=TOOL_DEFINITIONS,
    tool_handlers={
        "customer_get_360": _customer_get_360,
        "customer_get_summary": _customer_get_summary,
        "customer_get_transactions": _customer_get_transactions,
        "customer_get_profile": _customer_get_profile,
    },
)
