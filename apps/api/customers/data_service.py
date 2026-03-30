"""Centralized data service for customer profile and performance data."""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from apps.api.logging_config import get_logger

logger = get_logger(__name__)

# Base path for mock customer data, relative to the project root
MOCK_DATA_DIR = Path(__file__).resolve().parents[3] / "mocks" / "customer_data"

class DataService:
    """Service to load and prepare customer data from mock JSON files."""
    
    @staticmethod
    def _load_raw_json(customer_id: str) -> Dict[str, Any]:
        """Glob and load the raw JSON for a customer ID."""
        try:
            for file in MOCK_DATA_DIR.glob(f"{customer_id}_*.json"):
                with open(file, "r") as f:
                    return json.load(f)
        except Exception as e:
            logger.error("failed_to_load_customer_json", customer_id=customer_id, error=str(e))
        
        return {}

    @classmethod
    def get_customer_performance(cls, customer_id: str) -> Dict[str, Any]:
        """Prepare performance data structured for the dashboard frontend."""
        data = cls._load_raw_json(customer_id)
        if not data:
            return {}
            
        portfolio = data.get("portfolio", {})
        profile = data.get("profile", {})
        accounts = data.get("accounts", [])
        credit = data.get("credit", {})
        
        return {
            "portfolio_value": portfolio.get("portfolio_history", []),
            "asset_allocation": [
                {"label": k, "value": v["pct"]} 
                for k, v in portfolio.get("allocation", {}).items()
            ],
            "monthly_returns": portfolio.get("monthly_returns", []),
            "benchmark_comparison": portfolio.get("benchmark_comparison", []),
            "net_worth": {
                "customer": profile.get("full_name"),
                "customerId": customer_id,
                "asOf": portfolio.get("last_updated"),
                "assets": {
                    "liquidAssets": [
                        {
                            "label": acc["account_type"], 
                            "value": acc.get("balance", acc.get("total_sgd_equivalent", 0)), 
                            "note": acc["currency"]
                        }
                        for acc in accounts
                    ],
                    "investmentPortfolio": [
                        {"label": k, "value": v["value_sgd"]}
                        for k, v in portfolio.get("allocation", {}).items()
                    ],
                    "realEstate": [
                        {"label": re["property"], "value": re["value_sgd"]}
                        for re in data.get("real_estate", [])
                    ],
                    "otherAssets": []
                },
                "liabilities": [
                    {"label": "Lombard Facility", "value": -credit.get("lombard_facility", {}).get("drawn_sgd", 0)},
                    {"label": "Mortgage", "value": -credit.get("mortgage", {}).get("outstanding_sgd", 0)},
                ] + [
                    {"label": card["product"], "value": -card["outstanding_sgd"]}
                    for card in credit.get("credit_cards", [])
                ]
            },
            "insights": data.get("insights_signals", [])
        }

    @classmethod
    def get_customer_summary(cls, customer_id: str) -> Dict[str, Any]:
        """Prepare a high-level summary of the customer's profile and accounts."""
        data = cls._load_raw_json(customer_id)
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
            }
        }

    @classmethod
    def get_banking_context(cls, customer_id: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Prepare context specifically for the Private Banking chatbot agent."""
        data = cls._load_raw_json(customer_id)
        
        if not data:
            return {}, []

        profile = data.get("profile", {})
        portfolio = data.get("portfolio", {})
        
        # Robustly handle different currency suffixes or generic keys
        aum = profile.get("aum_with_ubs_sgd") or profile.get("aum_with_ubs_usd") or profile.get("aum") or 0
        net_worth = profile.get("net_worth_sgd") or profile.get("net_worth_usd") or profile.get("net_worth") or 0

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
            "derived_flags": profile.get("derived_flags", {})
        }
        
        accounts = [
            {
                "account_id": acc.get("account_id"),
                "type": acc.get("account_type"),
                "currency": acc.get("currency"),
                "balance": f"{acc.get('balance', acc.get('total_sgd_equivalent', acc.get('total_usd_equivalent', 0))):,.2f}"
            }
            for acc in data.get("accounts", [])
        ]
        
        return client, accounts

    @classmethod
    def get_advisory_context(cls, customer_id: str) -> Dict[str, Any]:
        """Prepare structured context for the Wealth Advisory agent."""
        data = cls._load_raw_json(customer_id)
        if not data:
            return {}

        profile = data.get("profile", {})
        portfolio = data.get("portfolio", {})
        currency = portfolio.get("currency", "SGD")
        aum = portfolio.get("total_value_sgd") or portfolio.get("total_value_usd") or portfolio.get("total_value") or 0
        net_worth = profile.get("net_worth_sgd") or profile.get("net_worth_usd") or profile.get("net_worth") or 0

        return {
            "customer_id": customer_id,
            "customer_name": profile.get("full_name"),
            "total_aum": f"{currency} {aum:,}",
            "net_worth": f"{currency} {net_worth:,}",
            "risk_profile": profile.get("risk_profile"),
            "asset_allocation": {
                k: f"{v['pct']}% ({currency} {v.get('value_sgd', v.get('value_usd', v.get('value', 0))):,})"
                for k, v in portfolio.get("allocation", {}).items()
            },
            "ytd_performance": f"+{portfolio.get('ytd_return_pct', 0)}%",
            "one_year_return": f"+{portfolio.get('one_year_return_pct', 0)}%",
            "risk_metrics": portfolio.get("risk_metrics", {}),
            "performance_attribution": portfolio.get("performance_attribution", {}),
            "benchmark_comparison": f"{portfolio.get('ytd_return_pct', 0)}% vs. {portfolio.get('benchmark', 'MSCI World benchmark')}"
        }

    @classmethod
    def get_lending_context(cls, customer_id: str) -> Dict[str, Any]:
        """Prepare structured context for the Lending & Credit agent."""
        data = cls._load_raw_json(customer_id)
        if not data:
            return {}

        portfolio = data.get("portfolio", {})
        credit = data.get("credit", {})
        lombard = credit.get("lombard_facility", {})
        currency = portfolio.get("currency", "SGD")
        aum = portfolio.get("total_value_sgd") or portfolio.get("total_value_usd") or portfolio.get("total_value") or 0
        
        l_limit = lombard.get('limit_sgd') or lombard.get('limit_usd') or lombard.get('limit') or 0
        l_drawn = lombard.get('drawn_sgd') or lombard.get('drawn_usd') or lombard.get('drawn') or 0
        l_avail = lombard.get('available_sgd') or lombard.get('available_usd') or lombard.get('available') or 0

        m_out = credit.get('mortgage', {}).get('outstanding_sgd') or credit.get('mortgage', {}).get('outstanding_usd') or credit.get('mortgage', {}).get('outstanding') or 0

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
                f"({credit.get('mortgage', {}).get('property', 'N/A')}) @ {credit.get('mortgage', {}).get('interest_rate_pct', 0)}% p.a."
            )
        }

    @classmethod
    def get_risk_analysis(cls, customer_id: str) -> Dict[str, Any]:
        """Fetch dedicated risk metrics for a customer."""
        data = cls._load_raw_json(customer_id)
        portfolio = data.get("portfolio", {})
        return {
            "risk_profile": data.get("profile", {}).get("risk_profile"),
            "metrics": portfolio.get("risk_metrics", {}),
            "system_triggers": [t for t in data.get("system_triggers", []) if t["type"] in ["Concentration", "Performance"]]
        }

    @classmethod
    def get_financial_planning(cls, customer_id: str) -> Dict[str, Any]:
        """Fetch goals, cashflow, and planning data."""
        data = cls._load_raw_json(customer_id)
        return {
            "goals": data.get("goals", []),
            "cashflow": data.get("cashflow", {}),
            "preferences": data.get("profile", {}).get("preferences", {})
        }

    @classmethod
    def get_compliance_context(cls, customer_id: str) -> Dict[str, Any]:
        """Fetch tax and regulatory context."""
        data = cls._load_raw_json(customer_id)
        profile = data.get("profile", {})
        return {
            "tax_profile": profile.get("tax_profile", {}),
            "kyc_status": profile.get("kyc_status"),
            "kyc_last_reviewed": profile.get("kyc_last_reviewed"),
            "system_triggers": [t for t in data.get("system_triggers", []) if t["type"] == "Regulatory"]
        }
