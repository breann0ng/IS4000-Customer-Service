"""Centralized data service for customer profile and performance data."""

from datetime import UTC, datetime
from typing import Any

from apps.api.customers.sqlite_repository import repository
from apps.api.logging_config import get_logger

logger = get_logger(__name__)


class DataService:
    """Service to load and prepare customer data from SQLite."""

    @staticmethod
    def _load_raw_json(customer_id: str) -> dict[str, Any]:
        """Load the normalized customer bundle for a customer ID."""
        try:
            return repository.build_customer_bundle(customer_id)
        except Exception as e:
            logger.error("failed_to_load_customer_data", customer_id=customer_id, error=str(e))

        return {}

    @classmethod
    def get_customer_performance(cls, customer_id: str) -> dict[str, Any]:
        """Prepare performance data structured for the dashboard frontend."""
        data = cls._load_raw_json(customer_id)
        return cls.get_customer_performance_from_bundle(customer_id, data)

    @staticmethod
    def _compound_return_percent(returns: list[dict[str, Any]]) -> float:
        """Compound a sequence of monthly percent returns into a single percent return."""
        growth = 1.0
        for entry in returns:
            try:
                value = float(entry.get("value", 0) or 0)
            except (TypeError, ValueError):
                value = 0.0
            growth *= 1.0 + (value / 100.0)
        return (growth - 1.0) * 100.0

    @staticmethod
    def get_customer_performance_from_bundle(
        customer_id: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Prepare performance payload from a pre-fetched customer bundle."""
        if not data:
            return {}

        portfolio = data.get("portfolio", {})
        profile = data.get("profile", {})
        accounts = data.get("accounts", [])
        credit = data.get("credit", {})
        as_of_date = datetime.now(UTC).strftime("%d %b %Y")

        portfolio_current_value = float(
            portfolio.get("total_value_usd")
            or portfolio.get("total_value_sgd")
            or profile.get("aum_with_ubs_usd")
            or profile.get("aum")
            or 0
        )

        monthly_returns = portfolio.get("monthly_returns", [])
        six_month_return_pct = (
            DataService._compound_return_percent(monthly_returns[-6:]) if monthly_returns else 0.0
        )
        benchmark_raw = portfolio.get("benchmark_comparison", [])
        monthly_by_month = {
            str(entry.get("month")): float(entry.get("value", 0) or 0)
            for entry in monthly_returns
            if entry.get("month") is not None
        }

        benchmark_comparison: list[dict[str, Any]] = []
        for entry in benchmark_raw:
            month = str(entry.get("month", ""))
            if "portfolio" in entry and "benchmark" in entry:
                benchmark_comparison.append(
                    {
                        "month": month,
                        "portfolio": float(entry.get("portfolio", 0) or 0),
                        "benchmark": float(entry.get("benchmark", 0) or 0),
                    }
                )
            else:
                benchmark_comparison.append(
                    {
                        "month": month,
                        "portfolio": float(monthly_by_month.get(month, 0) or 0),
                        "benchmark": float(entry.get("value", 0) or 0),
                    }
                )

        insights = [
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
            for index, signal in enumerate(data.get("insights_signals", []))
        ]

        return {
            "portfolio_current_value": portfolio_current_value,
            "portfolio_value": portfolio.get("portfolio_history", []),
            "asset_allocation": [
                {"label": k, "value": v.get("pct", 0)}
                for k, v in portfolio.get("allocation", {}).items()
            ],
            "monthly_returns": monthly_returns,
            "return_metrics": {
                "six_month_return_pct": round(six_month_return_pct, 2),
                "ytd_return_pct": float(portfolio.get("ytd_return_pct") or 0),
                "one_year_return_pct": float(portfolio.get("one_year_return_pct") or 0),
            },
            "risk_metrics": {
                "risk_profile": profile.get("risk_profile") or "N/A",
                "sharpe_ratio": float(portfolio.get("risk_metrics", {}).get("sharpe_ratio") or 0),
                "volatility_pct": float(
                    portfolio.get("risk_metrics", {}).get("volatility_pct") or 0
                ),
            },
            "benchmark_name": portfolio.get("benchmark") or "Benchmark",
            "relationship_manager": {
                "name": profile.get("relationship_manager") or "Relationship Manager",
                "email": profile.get("rm_email") or "",
                "phone": profile.get("rm_phone") or "",
            },
            "benchmark_comparison": benchmark_comparison,
            "net_worth": {
                "customer": profile.get("full_name"),
                "customerId": customer_id,
                "asOf": as_of_date,
                "assets": {
                    "liquidAssets": [
                        {
                            "label": acc.get("account_type"),
                            "value": acc.get("balance", acc.get("total_sgd_equivalent", 0)),
                            "note": acc.get("currency"),
                        }
                        for acc in accounts
                    ],
                    "investmentPortfolio": [
                        {"label": k, "value": v.get("value_sgd", v.get("value", 0))}
                        for k, v in portfolio.get("allocation", {}).items()
                    ],
                    "realEstate": [
                        {"label": re.get("property"), "value": re.get("value_sgd", 0)}
                        for re in data.get("real_estate", [])
                    ],
                    "otherAssets": [],
                },
                "liabilities": [
                    {
                        "label": "Lombard Facility",
                        "value": -credit.get("lombard_facility", {}).get("drawn_sgd", 0),
                    },
                    {
                        "label": "Mortgage",
                        "value": -credit.get("mortgage", {}).get("outstanding_sgd", 0),
                    },
                ]
                + [
                    {
                        "label": card.get("product", "Credit Card"),
                        "value": -card.get("outstanding_sgd", 0),
                    }
                    for card in credit.get("credit_cards", [])
                ],
            },
            "insights": insights,
        }

    @classmethod
    def get_customer_summary(cls, customer_id: str) -> dict[str, Any]:
        """Prepare a high-level summary of the customer's profile and accounts."""
        data = cls._load_raw_json(customer_id)
        return cls.get_customer_summary_from_bundle(data)

    @staticmethod
    def get_customer_summary_from_bundle(data: dict[str, Any]) -> dict[str, Any]:
        """Prepare customer summary payload from a pre-fetched customer bundle."""
        if not data:
            return {}

        portfolio = data.get("portfolio", {})

        return {
            "profile": data.get("profile"),
            "accounts": data.get("accounts"),
            "portfolio_summary": {
                "total_value": portfolio.get("total_value_sgd"),
                "currency": portfolio.get("currency"),
                "ytd_return": portfolio.get("ytd_return_pct"),
            },
        }

    @classmethod
    def get_banking_context(cls, customer_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Prepare context specifically for the Private Banking chatbot agent."""
        data = cls._load_raw_json(customer_id)

        if not data:
            return {}, []

        profile = data.get("profile", {})
        portfolio = data.get("portfolio", {})

        # Robustly handle different currency suffixes or generic keys
        aum = (
            profile.get("aum_with_ubs_sgd")
            or profile.get("aum_with_ubs_usd")
            or profile.get("aum")
            or 0
        )
        net_worth = (
            profile.get("net_worth_sgd")
            or profile.get("net_worth_usd")
            or profile.get("net_worth")
            or 0
        )

        client = {
            "customer_id": profile.get("customer_id"),
            "name": profile.get("full_name"),
            "relationship_manager": profile.get("relationship_manager"),
            "risk_profile": profile.get("risk_profile"),
            "aum_sgd": aum,
            "net_worth_sgd": net_worth,
            "ytd_return_pct": portfolio.get("ytd_return_pct"),
            "one_year_return_pct": portfolio.get("one_year_return_pct"),
            "preferences": profile.get("preferences", {}),
            "derived_flags": profile.get("derived_flags", {}),
        }

        accounts = []
        for acc in data.get("accounts", []):
            bal_fallback = acc.get("total_sgd_equivalent", acc.get("total_usd_equivalent", 0))
            bal = acc.get("balance", bal_fallback)
            accounts.append(
                {
                    "account_id": acc.get("account_id"),
                    "type": acc.get("account_type"),
                    "currency": acc.get("currency"),
                    "balance": f"{bal:,.2f}",
                }
            )

        return client, accounts

    @classmethod
    def get_advisory_context(cls, customer_id: str) -> dict[str, Any]:
        """Prepare structured context for the Wealth Advisory agent."""
        data = cls._load_raw_json(customer_id)
        if not data:
            return {}

        profile = data.get("profile", {})
        portfolio = data.get("portfolio", {})
        currency = portfolio.get("currency", "SGD")
        aum = (
            portfolio.get("total_value_sgd")
            or portfolio.get("total_value_usd")
            or portfolio.get("total_value")
            or 0
        )
        net_worth = (
            profile.get("net_worth_sgd")
            or profile.get("net_worth_usd")
            or profile.get("net_worth")
            or 0
        )

        asset_allocation = {}
        for k, v in portfolio.get("allocation", {}).items():
            alloc_val = v.get("value_sgd", v.get("value_usd", v.get("value", 0)))
            asset_allocation[k] = f"{v['pct']}% ({currency} {alloc_val:,})"
        ytd_pct = portfolio.get("ytd_return_pct", 0)
        benchmark = portfolio.get("benchmark", "MSCI World benchmark")
        benchmark_comparison = f"{ytd_pct}% vs. {benchmark}"

        return {
            "customer_id": customer_id,
            "customer_name": profile.get("full_name"),
            "total_aum": f"{currency} {aum:,}",
            "net_worth": f"{currency} {net_worth:,}",
            "risk_profile": profile.get("risk_profile"),
            "asset_allocation": asset_allocation,
            "ytd_performance": f"+{portfolio.get('ytd_return_pct', 0)}%",
            "one_year_return": f"+{portfolio.get('one_year_return_pct', 0)}%",
            "risk_metrics": portfolio.get("risk_metrics", {}),
            "performance_attribution": portfolio.get("performance_attribution", {}),
            "benchmark_comparison": benchmark_comparison,
        }

    @classmethod
    def get_lending_context(cls, customer_id: str) -> dict[str, Any]:
        """Prepare structured context for the Lending & Credit agent."""
        data = cls._load_raw_json(customer_id)
        if not data:
            return {}

        portfolio = data.get("portfolio", {})
        credit = data.get("credit", {})
        lombard = credit.get("lombard_facility", {})
        currency = portfolio.get("currency", "SGD")
        aum = (
            portfolio.get("total_value_sgd")
            or portfolio.get("total_value_usd")
            or portfolio.get("total_value")
            or 0
        )

        l_limit = lombard.get("limit_sgd") or lombard.get("limit_usd") or lombard.get("limit") or 0
        l_drawn = lombard.get("drawn_sgd") or lombard.get("drawn_usd") or lombard.get("drawn") or 0
        l_avail = (
            lombard.get("available_sgd")
            or lombard.get("available_usd")
            or lombard.get("available")
            or 0
        )

        m_out = (
            credit.get("mortgage", {}).get("outstanding_sgd")
            or credit.get("mortgage", {}).get("outstanding_usd")
            or credit.get("mortgage", {}).get("outstanding")
            or 0
        )

        return {
            "total_aum": f"{currency} {aum:,}",
            "ytd_return": f"+{portfolio.get('ytd_return_pct', 0)}%",
            "lombard_facility": (
                f"{currency} {l_limit:,} limit / "
                f"{currency} {l_drawn:,} drawn / "
                f"{currency} {l_avail:,} available @ {lombard.get('interest_rate_pct', 0)}% p.a."
            ),
            "mortgage": (
                f"{currency} {m_out:,} outstanding "
                f"({credit.get('mortgage', {}).get('property', 'N/A')}) @ "
                f"{credit.get('mortgage', {}).get('interest_rate_pct', 0)}% p.a."
            ),
        }

    @classmethod
    def get_risk_analysis(cls, customer_id: str) -> dict[str, Any]:
        """Fetch dedicated risk metrics for a customer."""
        data = cls._load_raw_json(customer_id)
        portfolio = data.get("portfolio", {})
        return {
            "risk_profile": data.get("profile", {}).get("risk_profile"),
            "metrics": portfolio.get("risk_metrics", {}),
            "system_triggers": [
                t
                for t in data.get("system_triggers", [])
                if t["type"] in ["Concentration", "Performance"]
            ],
        }

    @classmethod
    def get_financial_planning(cls, customer_id: str) -> dict[str, Any]:
        """Fetch goals, cashflow, and planning data."""
        data = cls._load_raw_json(customer_id)
        return {
            "goals": data.get("goals", []),
            "cashflow": data.get("cashflow", {}),
            "preferences": data.get("profile", {}).get("preferences", {}),
        }

    @classmethod
    def get_compliance_context(cls, customer_id: str) -> dict[str, Any]:
        """Fetch tax and regulatory context."""
        data = cls._load_raw_json(customer_id)
        profile = data.get("profile", {})
        return {
            "tax_profile": profile.get("tax_profile", {}),
            "kyc_status": profile.get("kyc_status"),
            "kyc_last_reviewed": profile.get("kyc_last_reviewed"),
            "system_triggers": [
                t for t in data.get("system_triggers", []) if t["type"] == "Regulatory"
            ],
        }
