"""Performance API routes backed by SQLite customer-data MCP."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from apps.api.auth.routes import get_current_user
from apps.api.customers.registry import USERNAME_TO_CUSTOMER_ID
from apps.api.customers.sqlite_repository import repository
from apps.api.database.models import User

router = APIRouter(prefix="/performance", tags=["performance"])

CUSTOMER_ID_BY_USERNAME: dict[str, str] = USERNAME_TO_CUSTOMER_ID


def _to_float(value: object) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _build_allocation_breakdown(allocation: dict[str, Any]) -> list[dict[str, float | str]]:
    mapping = [
        ("equities_percent", "Equities"),
        ("fixed_income_percent", "Fixed Income"),
        ("private_equity_percent", "Private Equity"),
        ("hedge_funds_percent", "Hedge Funds"),
        ("structured_products_percent", "Structured Products"),
        ("real_assets_cash_percent", "Real Assets & Cash"),
        ("cash_percent", "Cash"),
    ]

    breakdown: list[dict[str, float | str]] = []
    for key, label in mapping:
        value = _to_float(allocation.get(key))
        if value > 0:
            breakdown.append({"label": label, "value": value})

    return breakdown


@router.get("/overview")
async def get_performance_overview(
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Return live account-performance overview data for the logged-in demo user."""
    customer_id = CUSTOMER_ID_BY_USERNAME.get(current_user.username.lower())
    if not customer_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No mapped customer profile for this user",
        )

    result = repository.build_customer_bundle(customer_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="Unable to fetch customer data"
        )

    customer = result.get("profile") or {}
    accounts = result.get("accounts") or []
    portfolio = result.get("portfolio") or {}
    allocation = portfolio.get("allocation") or {}
    lending_summary = (result.get("lending") or {}).get("summary") or {}

    portfolio_value_usd = _to_float(allocation.get("total_portfolio_value_usd"))
    if portfolio_value_usd <= 0:
        portfolio_value_usd = _to_float(customer.get("aum_with_ubs_usd"))
    if portfolio_value_usd <= 0:
        portfolio_value_usd = _to_float(
            (portfolio.get("summary") or {}).get("total_holdings_value_usd")
        )

    return {
        "customer_id": customer_id,
        "customer_name": customer.get("full_name") or current_user.display_name,
        "as_of_date": allocation.get("snapshot_date") or portfolio.get("as_of_date"),
        "risk_profile": customer.get("risk_profile"),
        "portfolio_value_usd": portfolio_value_usd,
        "ytd_return_pct": allocation.get("ytd_performance_percent"),
        "accounts_total_usd": sum(_to_float(account.get("balance_usd")) for account in accounts),
        "allocation_breakdown": _build_allocation_breakdown(allocation),
        "available_credit_usd": _to_float(lending_summary.get("total_available_usd")),
        "drawn_credit_usd": _to_float(lending_summary.get("total_drawn_usd")),
        "card_outstanding_usd": _to_float(lending_summary.get("total_card_outstanding_usd")),
    }


@router.get("/monthly-returns")
async def get_monthly_returns(
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Return monthly returns data for the logged-in customer."""
    customer_id = CUSTOMER_ID_BY_USERNAME.get(current_user.username.lower())
    if not customer_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No mapped customer profile for this user",
        )

    result = repository.build_customer_bundle(customer_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to fetch customer data",
        )

    portfolio = result.get("portfolio") or {}
    monthly_returns = portfolio.get("monthly_returns") or result.get("monthly_returns") or []
    if not monthly_returns:
        monthly_returns = [
            {"month": "Oct-25", "value": 2.1},
            {"month": "Nov-25", "value": 3.6},
            {"month": "Dec-25", "value": -1.9},
            {"month": "Jan-26", "value": 4.0},
            {"month": "Feb-26", "value": 2.7},
            {"month": "Mar-26", "value": 2.8},
        ]

    return {
        "customer_id": customer_id,
        "data": [
            {
                "month": str(entry.get("month") or ""),
                "value": _to_float(entry.get("value")),
            }
            for entry in monthly_returns
        ],
    }


@router.get("/benchmark-comparison")
async def get_benchmark_comparison(
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Return portfolio vs benchmark comparison for the logged-in customer."""
    customer_id = CUSTOMER_ID_BY_USERNAME.get(current_user.username.lower())
    if not customer_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No mapped customer profile for this user",
        )

    result = repository.build_customer_bundle(customer_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to fetch customer data",
        )

    portfolio = result.get("portfolio") or {}
    benchmark_rows = (
        portfolio.get("benchmark_comparison") or result.get("benchmark_comparison") or []
    )

    monthly_returns = portfolio.get("monthly_returns") or []
    monthly_by_month = {
        str(entry.get("month") or ""): _to_float(entry.get("value")) for entry in monthly_returns
    }

    if not benchmark_rows:
        benchmark_rows = [
            {"month": "Oct-25", "portfolio": 2.1, "benchmark": 1.8},
            {"month": "Nov-25", "portfolio": 3.6, "benchmark": 2.5},
            {"month": "Dec-25", "portfolio": -1.9, "benchmark": -2.3},
            {"month": "Jan-26", "portfolio": 4.0, "benchmark": 3.1},
            {"month": "Feb-26", "portfolio": 2.7, "benchmark": 2.0},
            {"month": "Mar-26", "portfolio": 2.8, "benchmark": 1.9},
        ]

    comparison_data: list[dict[str, Any]] = []
    for row in benchmark_rows:
        month = str(row.get("month") or "")
        if "portfolio" in row and "benchmark" in row:
            comparison_data.append(
                {
                    "month": month,
                    "portfolio": _to_float(row.get("portfolio")),
                    "benchmark": _to_float(row.get("benchmark")),
                }
            )
        else:
            comparison_data.append(
                {
                    "month": month,
                    "portfolio": _to_float(monthly_by_month.get(month)),
                    "benchmark": _to_float(row.get("value")),
                }
            )

    return {
        "customer_id": customer_id,
        "data": comparison_data,
        "benchmark_label": portfolio.get("benchmark") or "Benchmark",
    }


@router.get("/insights")
async def get_performance_insights(
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Return curated insights and opportunities for the customer."""
    customer_id = CUSTOMER_ID_BY_USERNAME.get(current_user.username.lower())
    if not customer_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No mapped customer profile for this user",
        )

    result = repository.build_customer_bundle(customer_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to fetch customer data",
        )

    signals = result.get("insights_signals") or []
    if not signals:
        signals = [
            {
                "id": "INS-FALLBACK-1",
                "priority": "medium",
                "category": "Portfolio",
                "icon": "💡",
                "title": "Portfolio review available",
                "trigger": "Seeded customer profile loaded successfully",
                "summary": (
                    "This customer profile includes performance and wealth data for the dashboard."
                ),
                "suggested_actions": ["Review portfolio allocation", "Open monthly returns"],
                "rm_context": "Fallback insight created because no custom signal rows were found.",
                "tags": ["Fallback"],
            }
        ]

    return {
        "customer_id": customer_id,
        "signals": [
            {
                "id": signal.get("id") or f"INS-{index + 1:03d}",
                "priority": signal.get("priority") or "medium",
                "category": signal.get("category") or "Portfolio",
                "icon": signal.get("icon") or "💡",
                "title": signal.get("title") or "Portfolio insight",
                "trigger": signal.get("trigger") or "Customer activity signal",
                "summary": signal.get("summary") or "No summary available.",
                "suggested_actions": signal.get("suggested_actions") or [],
                "rm_context": signal.get("rm_context") or signal.get("summary") or "",
                "tags": signal.get("tags") or [],
            }
            for index, signal in enumerate(signals)
        ],
    }
