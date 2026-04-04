"""SQLite-backed customer data repository.

This module centralizes access to the demo customer dataset stored in
[data/customer_data.db](data/customer_data.db). It replaces the previous
static JSON file loader with structured reads from SQLite so both the FastAPI
app and the MCP servers can consume the same live customer context.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from apps.api.customers.registry import ALLOWED_CUSTOMER_IDS

DEFAULT_CUSTOMER_DATA_DB = Path(__file__).resolve().parents[3] / "data" / "customer_data.db"


class CustomerDataRepository:
    """Read-only repository for customer data stored in SQLite."""

    def __init__(self, db_path: Path | str = DEFAULT_CUSTOMER_DATA_DB) -> None:
        """Initialise the repository with the path to the SQLite database."""
        self.db_path = Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        if not self.db_path.exists():
            raise FileNotFoundError(f"Customer data database not found: {self.db_path}")

        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        return dict(row)

    def _fetch_all(
        self,
        query: str,
        params: tuple[Any, ...] = (),
    ) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def _fetch_one(
        self,
        query: str,
        params: tuple[Any, ...] = (),
    ) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(query, params).fetchone()
        return self._row_to_dict(row)

    def get_customer(self, customer_id: str) -> dict[str, Any] | None:
        """Return the customer row for a given customer ID."""
        if customer_id not in ALLOWED_CUSTOMER_IDS:
            return None
        return self._fetch_one(
            "SELECT * FROM customers WHERE customer_id = ?",
            (customer_id,),
        )

    def get_accounts(self, customer_id: str) -> list[dict[str, Any]]:
        """Return all accounts for a customer."""
        accounts = self._fetch_all(
            """
            SELECT *
            FROM accounts
            WHERE customer_id = ?
            ORDER BY account_id
            """,
            (customer_id,),
        )
        for account in accounts:
            account["balance"] = account.get("balance_usd") or 0.0
        return accounts

    def get_holdings(self, customer_id: str) -> list[dict[str, Any]]:
        """Return all holdings for a customer."""
        return self._fetch_all(
            """
            SELECT *
            FROM holdings
            WHERE customer_id = ?
            ORDER BY current_value_usd DESC, security_name ASC
            """,
            (customer_id,),
        )

    def get_credit_facilities(self, customer_id: str) -> list[dict[str, Any]]:
        """Return all credit facilities for a customer."""
        return self._fetch_all(
            """
            SELECT *
            FROM credit_facilities
            WHERE customer_id = ?
            ORDER BY facility_type, facility_name
            """,
            (customer_id,),
        )

    def get_mortgages(self, customer_id: str) -> list[dict[str, Any]]:
        """Return all mortgage records for a customer."""
        return self._fetch_all(
            """
            SELECT *
            FROM mortgages
            WHERE customer_id = ?
            ORDER BY maturity_date DESC, updated_at DESC
            """,
            (customer_id,),
        )

    def get_cards(self, customer_id: str) -> list[dict[str, Any]]:
        """Return all cards for a customer."""
        return self._fetch_all(
            """
            SELECT *
            FROM cards
            WHERE customer_id = ?
            ORDER BY card_name
            """,
            (customer_id,),
        )

    def get_portfolio_snapshot(self, customer_id: str) -> dict[str, Any] | None:
        """Return the most recent portfolio allocation snapshot for a customer."""
        return self._fetch_one(
            """
            SELECT *
            FROM portfolio_allocations
            WHERE customer_id = ?
            ORDER BY snapshot_date DESC, updated_at DESC
            LIMIT 1
            """,
            (customer_id,),
        )

    def get_portfolio_history(self, customer_id: str) -> list[dict[str, Any]]:
        """Return portfolio history series for a customer."""
        return self._fetch_all(
            """
            SELECT *
            FROM portfolio_history
            WHERE customer_id = ?
            ORDER BY year ASC, month ASC, month_label ASC
            """,
            (customer_id,),
        )

    def get_monthly_returns(self, customer_id: str) -> list[dict[str, Any]]:
        """Return monthly return series for a customer."""
        return self._fetch_all(
            """
            SELECT *
            FROM monthly_returns
            WHERE customer_id = ?
            ORDER BY year ASC, month ASC, month_label ASC
            """,
            (customer_id,),
        )

    def get_benchmark_comparison(self, customer_id: str) -> list[dict[str, Any]]:
        """Return benchmark comparison series for a customer."""
        return self._fetch_all(
            """
            SELECT *
            FROM benchmark_comparison
            WHERE customer_id = ?
            ORDER BY year ASC, month ASC, month_label ASC
            """,
            (customer_id,),
        )

    def get_transactions(
        self,
        customer_id: str,
        limit: int = 10,
        account_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return recent transactions for a customer, optionally scoped to an account."""
        query = [
            "SELECT *",
            "FROM transactions",
            "WHERE customer_id = ?",
        ]
        params: list[Any] = [customer_id]

        if account_id:
            query.append("AND account_id = ?")
            params.append(account_id)

        query.append("ORDER BY transaction_date DESC, created_at DESC")
        query.append("LIMIT ?")
        params.append(limit)

        return self._fetch_all("\n".join(query), tuple(params))

    def get_applications(self, customer_id: str) -> list[dict[str, Any]]:
        """Return product or service applications for a customer."""
        return self._fetch_all(
            """
            SELECT *
            FROM applications
            WHERE customer_id = ?
            ORDER BY submitted_date DESC, created_at DESC
            """,
            (customer_id,),
        )

    def get_appointments(self, customer_id: str) -> list[dict[str, Any]]:
        """Return appointments for a customer."""
        return self._fetch_all(
            """
            SELECT *
            FROM appointments
            WHERE customer_id = ?
            ORDER BY scheduled_datetime ASC, created_at DESC
            """,
            (customer_id,),
        )

    def get_kyc_review(self, customer_id: str) -> dict[str, Any] | None:
        """Return the latest KYC review record for a customer."""
        return self._fetch_one(
            """
            SELECT *
            FROM kyc_reviews
            WHERE customer_id = ?
            ORDER BY last_reviewed DESC, kyc_review_id DESC
            LIMIT 1
            """,
            (customer_id,),
        )

    def get_real_estate(self, customer_id: str) -> list[dict[str, Any]]:
        """Return all real estate properties for a customer."""
        rows = self._fetch_all(
            """
            SELECT property_id, customer_id, property_name as property,
                   location, value_sgd, loan_sgd
            FROM real_estate
            WHERE customer_id = ?
            ORDER BY property_id
            """,
            (customer_id,),
        )
        return rows

    def get_insights_signals(self, customer_id: str) -> list[dict[str, Any]]:
        """Return curated insights signals for a customer."""
        try:
            rows = self._fetch_all(
                """
                SELECT signal_id, customer_id, priority, category, icon, title, trigger,
                       summary, suggested_actions_json, rm_context, tags_json, display_order
                FROM insights_signals
                WHERE customer_id = ?
                ORDER BY display_order ASC, signal_id ASC
                """,
                (customer_id,),
            )
        except sqlite3.OperationalError:
            return []

        signals: list[dict[str, Any]] = []
        for row in rows:
            try:
                suggested_actions = json.loads(row.get("suggested_actions_json") or "[]")
            except (TypeError, ValueError, json.JSONDecodeError):
                suggested_actions = []
            try:
                tags = json.loads(row.get("tags_json") or "[]")
            except (TypeError, ValueError, json.JSONDecodeError):
                tags = []

            signals.append(
                {
                    "id": row.get("signal_id"),
                    "priority": row.get("priority"),
                    "category": row.get("category"),
                    "icon": row.get("icon"),
                    "title": row.get("title"),
                    "trigger": row.get("trigger"),
                    "summary": row.get("summary"),
                    "suggested_actions": suggested_actions,
                    "rm_context": row.get("rm_context"),
                    "tags": tags,
                }
            )
        return signals

    def build_customer_bundle(
        self, customer_id: str, transaction_limit: int = 10
    ) -> dict[str, Any]:
        """Build a normalized customer context bundle from SQLite tables."""
        if customer_id not in ALLOWED_CUSTOMER_IDS:
            return {}

        customer = self.get_customer(customer_id)
        if not customer:
            return {}

        accounts = self.get_accounts(customer_id)
        holdings = self.get_holdings(customer_id)
        credit_facilities = self.get_credit_facilities(customer_id)
        mortgages = self.get_mortgages(customer_id)
        cards = self.get_cards(customer_id)
        portfolio_snapshot = self.get_portfolio_snapshot(customer_id) or {}
        portfolio_history_rows = self.get_portfolio_history(customer_id)
        monthly_returns_rows = self.get_monthly_returns(customer_id)
        benchmark_rows = self.get_benchmark_comparison(customer_id)
        transactions = self.get_transactions(customer_id, limit=transaction_limit)
        applications = self.get_applications(customer_id)
        appointments = self.get_appointments(customer_id)
        kyc_review = self.get_kyc_review(customer_id) or {}

        total_holdings_value = sum(
            float(holding.get("current_value_usd") or 0) for holding in holdings
        )
        total_account_value = sum(float(account.get("balance_usd") or 0) for account in accounts)
        total_lombard_drawn = sum(
            float(facility.get("drawn_amount_usd") or 0)
            for facility in credit_facilities
            if (facility.get("facility_type") or "").lower() == "lombard"
        )
        total_lombard_limit = sum(
            float(facility.get("principal_usd") or 0)
            for facility in credit_facilities
            if (facility.get("facility_type") or "").lower() == "lombard"
        )
        total_lombard_available = sum(
            float(facility.get("available_amount_usd") or 0)
            for facility in credit_facilities
            if (facility.get("facility_type") or "").lower() == "lombard"
        )
        portfolio_value = float(
            portfolio_snapshot.get("total_portfolio_value_usd") or total_holdings_value
        )
        snapshot_ytd = portfolio_snapshot.get("ytd_performance_percent")
        ytd_return = (
            round(float(snapshot_ytd), 1)
            if snapshot_ytd is not None
            else self._estimate_ytd_return(portfolio_snapshot, holdings)
        )
        snapshot_one_year = portfolio_snapshot.get("one_year_performance_percent")
        one_year_return = (
            round(float(snapshot_one_year), 1)
            if snapshot_one_year is not None
            else round(ytd_return + 1.7, 1)
        )

        allocation = self._build_allocation_detail(portfolio_snapshot, portfolio_value)
        allocation_snapshot = {
            "snapshot_date": portfolio_snapshot.get("snapshot_date"),
            "equities_percent": portfolio_snapshot.get("equities_percent"),
            "fixed_income_percent": portfolio_snapshot.get("fixed_income_percent"),
            "private_equity_percent": portfolio_snapshot.get("private_equity_percent"),
            "hedge_funds_percent": portfolio_snapshot.get("hedge_funds_percent"),
            "real_assets_cash_percent": portfolio_snapshot.get("real_assets_cash_percent"),
            "commodities_percent": portfolio_snapshot.get("commodities_percent"),
            "crypto_percent": portfolio_snapshot.get("crypto_percent"),
            "structured_products_percent": portfolio_snapshot.get("structured_products_percent"),
            "cash_percent": portfolio_snapshot.get("cash_percent"),
            "other_percent": portfolio_snapshot.get("other_percent"),
            "total_portfolio_value_usd": portfolio_snapshot.get("total_portfolio_value_usd")
            or portfolio_value,
            "ytd_performance_percent": ytd_return,
            "one_year_performance_percent": one_year_return,
        }

        if monthly_returns_rows:
            monthly_returns = [
                {
                    "month": row.get("month_label") or f"{row.get('month')}",
                    "value": round(float(row.get("return_pct") or 0), 1),
                }
                for row in monthly_returns_rows
            ]
        else:
            monthly_returns = self._build_monthly_returns(ytd_return)

        if portfolio_history_rows:
            portfolio_history = [
                {
                    "month": row.get("month_label") or f"{row.get('month')}",
                    "value": round(float(row.get("portfolio_value_usd") or 0), 2),
                }
                for row in portfolio_history_rows
            ]
        else:
            portfolio_history = self._build_portfolio_history(portfolio_value, monthly_returns)

        if benchmark_rows:
            benchmark_comparison = [
                {
                    "month": row.get("month_label") or f"{row.get('month')}",
                    "portfolio": round(float(row.get("portfolio_return_pct") or 0), 1),
                    "benchmark": round(float(row.get("benchmark_return_pct") or 0), 1),
                }
                for row in benchmark_rows
            ]
        else:
            benchmark_comparison = self._build_benchmark_series(monthly_returns)
        risk_metrics = self._build_risk_metrics(allocation_snapshot, holdings, ytd_return)
        snapshot_sharpe = portfolio_snapshot.get("sharpe_ratio")
        snapshot_volatility = portfolio_snapshot.get("volatility_pct")
        if snapshot_sharpe is not None:
            risk_metrics["sharpe_ratio"] = round(float(snapshot_sharpe), 2)
        if snapshot_volatility is not None:
            risk_metrics["volatility_pct"] = round(float(snapshot_volatility), 1)
        performance_attribution = {
            "selection_effect_pct": round(max(ytd_return - 0.8, 0.0), 1),
            "allocation_effect_pct": round(max(ytd_return - 1.4, 0.0), 1),
            "other_effect_pct": round(ytd_return * 0.12, 1),
        }
        tax_profile = self._build_tax_profile(customer)
        derived_flags = self._build_derived_flags(
            customer, accounts, holdings, kyc_review, credit_facilities
        )
        goals = self._build_goals(applications)
        cashflow = self._build_cashflow(transactions)
        system_triggers = self._build_system_triggers(holdings, kyc_review, credit_facilities)
        insights = self.get_insights_signals(customer_id)
        if not insights:
            insights = self._build_insights(
                customer, portfolio_value, ytd_return, holdings, credit_facilities
            )

        profile = {
            **customer,
            "preferences": {
                "preferred_contact": customer.get("preferred_contact"),
                "language": customer.get("language"),
            },
            "derived_flags": derived_flags,
            "tax_profile": tax_profile,
            "kyc_status": kyc_review.get("kyc_status"),
            "kyc_last_reviewed": kyc_review.get("last_reviewed"),
            "aum_with_ubs_usd": customer.get("aum_with_ubs_usd") or total_account_value,
            "aum": customer.get("aum_with_ubs_usd") or total_account_value,
            "net_worth_usd": customer.get("net_worth_usd") or portfolio_value,
            "net_worth": customer.get("net_worth_usd") or portfolio_value,
            "ytd_return_pct": ytd_return,
            "one_year_return_pct": one_year_return,
        }

        credit = {
            "lombard_facility": {
                "limit_usd": total_lombard_limit,
                "limit_sgd": total_lombard_limit,
                "drawn_usd": total_lombard_drawn,
                "drawn_sgd": total_lombard_drawn,
                "available_usd": total_lombard_available,
                "available_sgd": total_lombard_available,
                "interest_rate_pct": self._primary_lombard_rate(credit_facilities),
            },
            "mortgage": self._build_mortgage_context(customer_id),
            "credit_cards": [
                {
                    "product": card.get("card_name") or card.get("card_type") or "Card",
                    "outstanding_usd": float(card.get("outstanding_balance_usd") or 0),
                    "outstanding_sgd": float(card.get("outstanding_balance_usd") or 0),
                    "credit_limit_usd": float(card.get("credit_limit_usd") or 0),
                    "credit_limit_sgd": float(card.get("credit_limit_usd") or 0),
                    "status": card.get("status"),
                }
                for card in cards
            ],
        }

        return {
            "profile": profile,
            "accounts": accounts,
            "cards": cards,
            "portfolio": {
                "currency": "USD",
                "total_value_usd": portfolio_value,
                "total_value_sgd": portfolio_value,
                "ytd_return_pct": ytd_return,
                "one_year_return_pct": one_year_return,
                "last_updated": portfolio_snapshot.get("snapshot_date"),
                "allocation_snapshot": allocation_snapshot,
                "portfolio_history": portfolio_history,
                "monthly_returns": monthly_returns,
                "benchmark_comparison": benchmark_comparison,
                "allocation": allocation,
                "risk_metrics": risk_metrics,
                "performance_attribution": performance_attribution,
                "benchmark": portfolio_snapshot.get("benchmark_name") or "MSCI World",
                "summary": {
                    "total_holdings_value_usd": total_holdings_value,
                    "total_accounts_value_usd": total_account_value,
                },
            },
            "credit": credit,
            "real_estate": self.get_real_estate(customer_id),
            "goals": goals,
            "cashflow": cashflow,
            "system_triggers": system_triggers,
            "insights_signals": insights,
            "transactions": transactions,
            "applications": applications,
            "appointments": appointments,
            "kyc": kyc_review,
            "mortgages": mortgages,
        }

    @staticmethod
    def _estimate_ytd_return(
        portfolio_snapshot: dict[str, Any],
        holdings: list[dict[str, Any]],
    ) -> float:
        equities = float(portfolio_snapshot.get("equities_percent") or 0)
        private_equity = float(portfolio_snapshot.get("private_equity_percent") or 0)
        cash = float(portfolio_snapshot.get("cash_percent") or 0)
        concentration_penalty = 0.0
        if holdings:
            total = sum(float(holding.get("current_value_usd") or 0) for holding in holdings)
            largest = max(float(holding.get("current_value_usd") or 0) for holding in holdings)
            if total > 0:
                concentration_penalty = (largest / total) * 2.0
        estimate = (
            1.8 + equities * 0.06 + private_equity * 0.05 - cash * 0.04 - concentration_penalty
        )
        return round(max(estimate, -10.0), 1)

    @staticmethod
    def _build_allocation_detail(
        portfolio_snapshot: dict[str, Any],
        portfolio_value: float,
    ) -> dict[str, dict[str, float]]:
        mapping = [
            ("Equities", "equities_percent"),
            ("Fixed Income", "fixed_income_percent"),
            ("Private Equity", "private_equity_percent"),
            ("Commodities", "commodities_percent"),
            ("Crypto", "crypto_percent"),
            ("Structured Products", "structured_products_percent"),
            ("Cash", "cash_percent"),
            ("Other", "other_percent"),
        ]
        allocation: dict[str, dict[str, float]] = {}
        for label, key in mapping:
            pct = float(portfolio_snapshot.get(key) or 0)
            if pct <= 0:
                continue
            allocation[label] = {
                "pct": round(pct, 1),
                "value_sgd": round(portfolio_value * pct / 100.0, 2),
                "value_usd": round(portfolio_value * pct / 100.0, 2),
                "value": round(portfolio_value * pct / 100.0, 2),
            }
        return allocation

    @staticmethod
    def _build_monthly_returns(ytd_return: float) -> list[dict[str, float]]:
        base = [
            ytd_return - 1.8,
            ytd_return - 0.6,
            ytd_return - 2.1,
            ytd_return + 0.7,
            ytd_return - 0.3,
            ytd_return,
        ]
        months = ["Oct", "Nov", "Dec", "Jan", "Feb", "Mar"]
        return [
            {"month": month, "value": round(value, 1)}
            for month, value in zip(months, base, strict=True)
        ]

    @staticmethod
    def _build_portfolio_history(
        portfolio_value: float,
        monthly_returns: list[dict[str, float]],
    ) -> list[dict[str, float]]:
        current = portfolio_value
        history: list[dict[str, float]] = []
        for entry in reversed(monthly_returns):
            current = (
                current / (1.0 + (entry["value"] / 100.0)) if entry["value"] > -99 else current
            )
            history.append({"month": entry["month"], "value": round(current, 2)})
        return list(reversed(history))

    @staticmethod
    def _build_benchmark_series(monthly_returns: list[dict[str, float]]) -> list[dict[str, float]]:
        offsets = [0.3, 0.6, 0.4, 0.9, 0.5, 0.4]
        return [
            {"month": entry["month"], "value": round(entry["value"] - offsets[index], 1)}
            for index, entry in enumerate(monthly_returns)
        ]

    @staticmethod
    def _build_risk_metrics(
        allocation_snapshot: dict[str, Any],
        holdings: list[dict[str, Any]],
        ytd_return: float,
    ) -> dict[str, float]:
        equities = float(allocation_snapshot.get("equities_percent") or 0)
        private_equity = float(allocation_snapshot.get("private_equity_percent") or 0)
        total_holdings = (
            sum(float(holding.get("current_value_usd") or 0) for holding in holdings) or 1.0
        )
        largest_holding = max(
            (float(holding.get("current_value_usd") or 0) for holding in holdings), default=0.0
        )
        concentration = round((largest_holding / total_holdings) * 100.0, 1)
        volatility = round(5.5 + equities * 0.05 + private_equity * 0.04 + concentration * 0.03, 1)
        sharpe = round(ytd_return / volatility if volatility else 0.0, 2)
        value_at_risk = round(total_holdings * (volatility / 100.0) * 1.65, 2)
        return {
            "volatility_pct": volatility,
            "sharpe_ratio": sharpe,
            "value_at_risk_usd": value_at_risk,
            "concentration_pct": concentration,
        }

    @staticmethod
    def _build_tax_profile(customer: dict[str, Any]) -> dict[str, Any]:
        return {
            "tax_residency": customer.get("tax_residency"),
            "nationality": customer.get("nationality"),
            "preferred_language": customer.get("language"),
        }

    @staticmethod
    def _build_derived_flags(
        customer: dict[str, Any],
        accounts: list[dict[str, Any]],
        holdings: list[dict[str, Any]],
        kyc_review: dict[str, Any],
        credit_facilities: list[dict[str, Any]],
    ) -> dict[str, Any]:
        total_holdings = (
            sum(float(holding.get("current_value_usd") or 0) for holding in holdings) or 1.0
        )
        largest_holding = max(
            (float(holding.get("current_value_usd") or 0) for holding in holdings), default=0.0
        )
        concentration_pct = round((largest_holding / total_holdings) * 100.0, 1)
        cross_border = (
            "High"
            if len({account.get("currency") for account in accounts if account.get("currency")}) > 1
            else "Moderate"
        )
        if (
            customer.get("tax_residency")
            and customer.get("nationality")
            and customer.get("tax_residency") != customer.get("nationality")
        ):
            cross_border = "High"
        if any(
            (facility.get("facility_type") or "").lower() == "lombard"
            for facility in credit_facilities
        ):
            lending = "Active"
        else:
            lending = "None"
        return {
            "cross_border_exposure": cross_border,
            "portfolio_concentration_pct": concentration_pct,
            "needs_kyc_refresh": (kyc_review.get("kyc_status") or "").lower() != "verified",
            "lending_profile": lending,
        }

    @staticmethod
    def _build_goals(applications: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "goal": application.get("product_name") or application.get("application_type"),
                "status": application.get("status"),
                "target_date": application.get("expected_completion_date"),
            }
            for application in applications
        ]

    @staticmethod
    def _build_cashflow(transactions: list[dict[str, Any]]) -> dict[str, Any]:
        credit_inflows = sum(
            float(txn.get("amount_usd") or 0)
            for txn in transactions
            if float(txn.get("amount_usd") or 0) > 0
        )
        debits = sum(
            abs(float(txn.get("amount_usd") or 0))
            for txn in transactions
            if float(txn.get("amount_usd") or 0) < 0
        )
        return {
            "recent_credits_usd": round(credit_inflows, 2),
            "recent_debits_usd": round(debits, 2),
            "net_flow_usd": round(credit_inflows - debits, 2),
        }

    @staticmethod
    def _build_system_triggers(
        holdings: list[dict[str, Any]],
        kyc_review: dict[str, Any],
        credit_facilities: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        triggers: list[dict[str, Any]] = []
        total_holdings = (
            sum(float(holding.get("current_value_usd") or 0) for holding in holdings) or 1.0
        )
        if holdings:
            largest = max(
                holdings, key=lambda holding: float(holding.get("current_value_usd") or 0)
            )
            largest_pct = (float(largest.get("current_value_usd") or 0) / total_holdings) * 100.0
            if largest_pct >= 25:
                triggers.append(
                    {
                        "type": "Concentration",
                        "severity": "high",
                        "message": (
                            f"{largest.get('security_name')} represents "
                            f"{largest_pct:.1f}% of tracked holdings."
                        ),
                    }
                )
        if (kyc_review.get("kyc_status") or "").lower() != "verified":
            triggers.append(
                {
                    "type": "Regulatory",
                    "severity": "medium",
                    "message": "KYC review requires attention.",
                }
            )
        if any(float(facility.get("drawn_amount_usd") or 0) > 0 for facility in credit_facilities):
            triggers.append(
                {
                    "type": "Performance",
                    "severity": "medium",
                    "message": (
                        "Lombard activity is active and should be reviewed "
                        "alongside portfolio performance."
                    ),
                }
            )
        return triggers

    @staticmethod
    def _build_insights(
        customer: dict[str, Any],
        portfolio_value: float,
        ytd_return: float,
        holdings: list[dict[str, Any]],
        credit_facilities: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        top_holding = max(
            holdings, key=lambda holding: float(holding.get("current_value_usd") or 0), default=None
        )
        insights: list[dict[str, Any]] = []
        if top_holding is not None:
            insights.append(
                {
                    "id": "INS-001",
                    "priority": "high",
                    "category": "Portfolio Concentration",
                    "title": f"Review exposure to {top_holding.get('security_name')}",
                    "summary": (
                        f"{top_holding.get('security_name')} is the largest holding "
                        f"against a portfolio value of USD {portfolio_value:,.0f}."
                    ),
                    "suggested_actions": [
                        "Review concentration limits with the relationship manager",
                        "Stress-test downside scenarios",
                        "Confirm whether the position is strategic or tactical",
                    ],
                }
            )
        if any(
            (facility.get("facility_type") or "").lower() == "lombard"
            for facility in credit_facilities
        ):
            insights.append(
                {
                    "id": "INS-002",
                    "priority": "medium",
                    "category": "Credit Utilisation",
                    "title": "Monitor Lombard utilisation",
                    "summary": (
                        "The customer has active lending facilities while "
                        f"YTD performance is estimated at {ytd_return:.1f}%."
                    ),
                    "suggested_actions": [
                        "Check available lending headroom",
                        "Compare borrowing cost with expected portfolio return",
                        "Review refinancing opportunities",
                    ],
                }
            )
        return insights

    @staticmethod
    def _primary_lombard_rate(credit_facilities: list[dict[str, Any]]) -> float:
        for facility in credit_facilities:
            if (facility.get("facility_type") or "").lower() == "lombard":
                return float(facility.get("interest_rate") or 0)
        return 0.0

    @staticmethod
    def _build_mortgage_context(customer_id: str) -> dict[str, Any]:
        mortgages = repository.get_mortgages(customer_id)
        if not mortgages:
            return {
                "outstanding_usd": 0.0,
                "outstanding_sgd": 0.0,
                "interest_rate_pct": 0.0,
                "property": "N/A",
                "status": "Unavailable",
                "customer_id": customer_id,
            }

        mortgage = mortgages[0]
        outstanding_sgd = float(mortgage.get("outstanding_sgd") or 0)
        outstanding_usd = float(mortgage.get("outstanding_usd") or outstanding_sgd)
        return {
            "product": mortgage.get("product"),
            "property": mortgage.get("property"),
            "outstanding_usd": outstanding_usd,
            "outstanding_sgd": outstanding_sgd,
            "original_amount_sgd": mortgage.get("original_amount_sgd"),
            "interest_rate_pct": mortgage.get("interest_rate_pct") or 0.0,
            "monthly_repayment_sgd": mortgage.get("monthly_repayment_sgd"),
            "maturity_date": mortgage.get("maturity_date"),
            "status": mortgage.get("status"),
            "customer_id": customer_id,
        }


repository = CustomerDataRepository()
