"""Rebuild the demo SQLite customer database from the 3 approved profiles.

This script seeds only:
- C-001 John Smith
- C-002 Alice Johnson
- C-003 Marcus Tan

It creates a fresh `data/customer_data.db` database and populates the
normalized tables used by the app and MCP wrapper.
"""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "mocks" / "customer_data"
DB_PATH = ROOT / "data" / "customer_data.db"
KEEP_FILES = [
    DATA_DIR / "C-001_john_smith.json",
    DATA_DIR / "C-002_alice_johnson.json",
    DATA_DIR / "C-003_marcus_tan.json",
]


SCHEMA_SQL = """
DROP TABLE IF EXISTS real_estate;
DROP TABLE IF EXISTS insights_signals;
DROP TABLE IF EXISTS mortgages;
DROP TABLE IF EXISTS accounts;
DROP TABLE IF EXISTS holdings;
DROP TABLE IF EXISTS credit_facilities;
DROP TABLE IF EXISTS cards;
DROP TABLE IF EXISTS portfolio_allocations;
DROP TABLE IF EXISTS portfolio_history;
DROP TABLE IF EXISTS monthly_returns;
DROP TABLE IF EXISTS benchmark_comparison;
DROP TABLE IF EXISTS transactions;
DROP TABLE IF EXISTS applications;
DROP TABLE IF EXISTS appointments;
DROP TABLE IF EXISTS kyc_reviews;
DROP TABLE IF EXISTS customers;

CREATE TABLE customers (
    customer_id TEXT PRIMARY KEY,
    full_name TEXT NOT NULL,
    preferred_name TEXT,
    date_of_birth TEXT,
    nationality TEXT,
    tax_residency TEXT,
    segment TEXT,
    tier TEXT,
    relationship_manager TEXT,
    rm_email TEXT,
    rm_phone TEXT,
    onboarded_date TEXT,
    preferred_contact TEXT,
    language TEXT,
    risk_profile TEXT,
    net_worth_usd REAL,
    aum_with_ubs_usd REAL,
    email TEXT,
    mobile TEXT,
    address TEXT,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE accounts (
    account_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    account_name TEXT,
    account_type TEXT,
    currency TEXT,
    balance_usd REAL,
    status TEXT,
    opened_date TEXT,
    updated_date TEXT
);

CREATE TABLE holdings (
    holding_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    account_id TEXT,
    security_name TEXT,
    ticker TEXT,
    asset_class TEXT,
    currency TEXT,
    quantity REAL,
    cost_basis_usd REAL,
    current_value_usd REAL,
    unrealized_gain_loss_usd REAL,
    sector TEXT,
    acquisition_date TEXT,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE credit_facilities (
    facility_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    facility_type TEXT,
    facility_name TEXT,
    currency TEXT,
    principal_usd REAL,
    drawn_amount_usd REAL,
    available_amount_usd REAL,
    interest_rate REAL,
    interest_accrued_usd REAL,
    status TEXT,
    originated_date TEXT,
    maturity_date TEXT,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE mortgages (
    mortgage_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    product TEXT,
    property TEXT,
    outstanding_usd REAL,
    outstanding_sgd REAL,
    original_amount_sgd REAL,
    interest_rate_pct REAL,
    monthly_repayment_sgd REAL,
    maturity_date TEXT,
    status TEXT,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE cards (
    card_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    account_id TEXT,
    card_type TEXT,
    card_name TEXT,
    card_number_masked TEXT,
    status TEXT,
    credit_limit_usd REAL,
    outstanding_balance_usd REAL,
    annual_fee_usd REAL,
    renewal_date TEXT,
    expiry_date TEXT,
    issued_date TEXT,
    created_at TEXT
);

CREATE TABLE portfolio_allocations (
    allocation_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    snapshot_date TEXT,
    equities_percent REAL,
    fixed_income_percent REAL,
    private_equity_percent REAL,
    hedge_funds_percent REAL,
    real_assets_cash_percent REAL,
    commodities_percent REAL,
    crypto_percent REAL,
    structured_products_percent REAL,
    cash_percent REAL,
    other_percent REAL,
    total_portfolio_value_usd REAL,
    ytd_performance_percent REAL,
    one_year_performance_percent REAL,
    sharpe_ratio REAL,
    volatility_pct REAL,
    benchmark_name TEXT,
    updated_at TEXT
);

CREATE TABLE portfolio_history (
    history_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    year INTEGER,
    month INTEGER,
    month_label TEXT,
    portfolio_value_usd REAL,
    created_at TEXT
);

CREATE TABLE monthly_returns (
    return_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    year INTEGER,
    month INTEGER,
    month_label TEXT,
    return_pct REAL,
    created_at TEXT
);

CREATE TABLE benchmark_comparison (
    benchmark_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    year INTEGER,
    month INTEGER,
    month_label TEXT,
    portfolio_return_pct REAL,
    benchmark_return_pct REAL,
    created_at TEXT
);

CREATE TABLE transactions (
    transaction_id TEXT PRIMARY KEY,
    account_id TEXT,
    customer_id TEXT NOT NULL,
    transaction_date TEXT,
    amount_usd REAL,
    currency TEXT,
    description TEXT,
    type TEXT,
    merchant TEXT,
    category TEXT,
    status TEXT,
    dispute_reason TEXT,
    created_at TEXT
);

CREATE TABLE applications (
    application_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    application_type TEXT,
    product_name TEXT,
    status TEXT,
    amount_or_limit_usd REAL,
    submitted_date TEXT,
    expected_completion_date TEXT,
    notes TEXT,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE appointments (
    appointment_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    relationship_manager_id TEXT,
    appointment_type TEXT,
    scheduled_datetime TEXT,
    duration_minutes INTEGER,
    location TEXT,
    status TEXT,
    notes TEXT,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE kyc_reviews (
    kyc_review_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL,
    kyc_status TEXT,
    last_reviewed TEXT,
    next_due_date TEXT,
    documents_required TEXT,
    document_status TEXT,
    notes TEXT,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE real_estate (
    property_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    property_name TEXT,
    location TEXT,
    value_sgd REAL,
    loan_sgd REAL,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE insights_signals (
    signal_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    priority TEXT,
    category TEXT,
    icon TEXT,
    title TEXT,
    trigger TEXT,
    summary TEXT,
    suggested_actions_json TEXT,
    rm_context TEXT,
    tags_json TEXT,
    display_order INTEGER,
    created_at TEXT,
    updated_at TEXT
);
"""


def now_ts() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "item"


def load_profile(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def first_non_null(*values: Any, default: Any = None) -> Any:
    for value in values:
        if value is not None:
            return value
    return default


def account_balance_usd(account: dict[str, Any]) -> float:
    if account.get("balance") is not None:
        return float(account["balance"])
    if account.get("total_sgd_equivalent") is not None:
        return float(account["total_sgd_equivalent"])
    if account.get("total_usd_equivalent") is not None:
        return float(account["total_usd_equivalent"])
    balances = account.get("balances")
    if isinstance(balances, dict) and balances:
        return float(sum(float(value) for value in balances.values()))
    return 0.0


def currency_from_account(account: dict[str, Any]) -> str:
    return str(account.get("currency") or "USD")


def value_and_currency(item: dict[str, Any], value_keys: list[str]) -> tuple[float, str]:
    for key in value_keys:
        if item.get(key) is not None:
            key_currency = key.split("_")[-1].upper() if "_" in key else "USD"
            return float(item[key]), key_currency
    return 0.0, "USD"


def parse_month_label(label: str) -> tuple[int | None, int | None]:
    parts = str(label).split("-")
    if len(parts) != 2:
        return None, None

    month_map = {
        "Jan": 1,
        "Feb": 2,
        "Mar": 3,
        "Apr": 4,
        "May": 5,
        "Jun": 6,
        "Jul": 7,
        "Aug": 8,
        "Sep": 9,
        "Oct": 10,
        "Nov": 11,
        "Dec": 12,
    }

    month_num = month_map.get(parts[0])
    try:
        year_num = 2000 + int(parts[1])
    except ValueError:
        year_num = None

    return year_num, month_num


def insert_customer_rows(cursor: sqlite3.Cursor, profile: dict[str, Any]) -> None:
    meta = profile["profile"]
    customer_id = meta["customer_id"]
    timestamp = now_ts()
    cursor.execute(
        """
        INSERT INTO customers (
            customer_id, full_name, preferred_name, date_of_birth, nationality,
            tax_residency, segment, tier, relationship_manager, rm_email, rm_phone,
            onboarded_date, preferred_contact, language, risk_profile, net_worth_usd,
            aum_with_ubs_usd, email, mobile, address, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            customer_id,
            meta.get("full_name"),
            meta.get("preferred_name"),
            meta.get("date_of_birth"),
            meta.get("nationality"),
            meta.get("tax_residency"),
            meta.get("segment"),
            meta.get("tier"),
            meta.get("relationship_manager"),
            meta.get("rm_email"),
            meta.get("rm_phone"),
            meta.get("onboarded_date"),
            meta.get("preferred_contact"),
            meta.get("language"),
            meta.get("risk_profile"),
            first_non_null(meta.get("net_worth_usd"), meta.get("net_worth_sgd"), default=0.0),
            first_non_null(meta.get("aum_with_ubs_usd"), meta.get("aum_with_ubs_sgd"), default=0.0),
            meta.get("email"),
            meta.get("mobile"),
            meta.get("address"),
            timestamp,
            timestamp,
        ),
    )


def insert_accounts(cursor: sqlite3.Cursor, profile: dict[str, Any]) -> None:
    customer_id = profile["profile"]["customer_id"]
    timestamp = now_ts()
    for account in profile.get("accounts", []):
        account_id = str(account.get("account_id") or f"ACC-{customer_id}-{slugify(account.get('account_type', 'account'))}")
        cursor.execute(
            """
            INSERT INTO accounts (
                account_id, customer_id, account_name, account_type, currency,
                balance_usd, status, opened_date, updated_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                account_id,
                customer_id,
                account.get("account_name") or account.get("account_type"),
                account.get("account_type"),
                currency_from_account(account),
                account_balance_usd(account),
                account.get("status"),
                account.get("opened_date"),
                timestamp,
            ),
        )


def insert_holdings(cursor: sqlite3.Cursor, profile: dict[str, Any]) -> None:
    customer_id = profile["profile"]["customer_id"]
    timestamp = now_ts()

    for holding in profile.get("portfolio", {}).get("top_equity_holdings", []):
        value, currency = value_and_currency(holding, ["value_usd", "value_sgd"])
        ticker = holding.get("ticker") or slugify(holding.get("name", "holding")).upper()
        cursor.execute(
            """
            INSERT INTO holdings (
                holding_id, customer_id, account_id, security_name, ticker, asset_class,
                currency, quantity, cost_basis_usd, current_value_usd, unrealized_gain_loss_usd,
                sector, acquisition_date, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"HLD-{customer_id}-{slugify(ticker)}",
                customer_id,
                None,
                holding.get("name"),
                ticker,
                "Equity",
                currency,
                None,
                None,
                value,
                None,
                holding.get("sector"),
                None,
                timestamp,
                timestamp,
            ),
        )

    for market in profile.get("portfolio", {}).get("private_markets", []):
        value, currency = value_and_currency(market, ["nav_usd", "nav_sgd"])
        cursor.execute(
            """
            INSERT INTO holdings (
                holding_id, customer_id, account_id, security_name, ticker, asset_class,
                currency, quantity, cost_basis_usd, current_value_usd, unrealized_gain_loss_usd,
                sector, acquisition_date, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"HLD-{customer_id}-{slugify(market.get('fund', 'private-market'))}",
                customer_id,
                None,
                market.get("fund"),
                None,
                market.get("type") or "Private Market",
                currency,
                None,
                first_non_null(market.get("commitment_usd"), market.get("commitment_sgd")),
                value,
                None,
                market.get("type"),
                None,
                timestamp,
                timestamp,
            ),
        )

    for product in profile.get("portfolio", {}).get("structured_products", []):
        value, currency = value_and_currency(product, ["value_usd", "value_sgd"])
        cursor.execute(
            """
            INSERT INTO holdings (
                holding_id, customer_id, account_id, security_name, ticker, asset_class,
                currency, quantity, cost_basis_usd, current_value_usd, unrealized_gain_loss_usd,
                sector, acquisition_date, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"HLD-{customer_id}-{slugify(product.get('name', 'structured-product'))}",
                customer_id,
                None,
                product.get("name"),
                None,
                "Structured Product",
                currency,
                None,
                None,
                value,
                None,
                product.get("underlying"),
                product.get("maturity"),
                timestamp,
                timestamp,
            ),
        )


def insert_credit(cursor: sqlite3.Cursor, profile: dict[str, Any]) -> None:
    customer_id = profile["profile"]["customer_id"]
    timestamp = now_ts()
    lombard = profile.get("credit", {}).get("lombard_facility")
    if lombard:
        limit_value, currency = value_and_currency(lombard, ["limit_usd", "limit_sgd"])
        drawn_value, _ = value_and_currency(lombard, ["drawn_usd", "drawn_sgd"])
        available_value, _ = value_and_currency(lombard, ["available_usd", "available_sgd"])
        cursor.execute(
            """
            INSERT INTO credit_facilities (
                facility_id, customer_id, facility_type, facility_name, currency,
                principal_usd, drawn_amount_usd, available_amount_usd, interest_rate,
                interest_accrued_usd, status, originated_date, maturity_date, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"LMB-{customer_id}",
                customer_id,
                "Lombard",
                lombard.get("product") or "Lombard Credit Facility",
                currency,
                limit_value,
                drawn_value,
                available_value,
                lombard.get("interest_rate_pct"),
                None,
                lombard.get("status"),
                None,
                None,
                timestamp,
                timestamp,
            ),
        )

    mortgage = profile.get("credit", {}).get("mortgage")
    if mortgage:
        outstanding_sgd = float(mortgage.get("outstanding_sgd") or 0)
        cursor.execute(
            """
            INSERT INTO mortgages (
                mortgage_id, customer_id, product, property, outstanding_usd, outstanding_sgd,
                original_amount_sgd, interest_rate_pct, monthly_repayment_sgd, maturity_date,
                status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"MORT-{customer_id}",
                customer_id,
                mortgage.get("product"),
                mortgage.get("property"),
                outstanding_sgd,
                outstanding_sgd,
                mortgage.get("original_amount_sgd"),
                mortgage.get("interest_rate_pct"),
                mortgage.get("monthly_repayment_sgd"),
                mortgage.get("maturity_date"),
                mortgage.get("status"),
                timestamp,
                timestamp,
            ),
        )

    for property in profile.get("real_estate", []):
        cursor.execute(
            """
            INSERT INTO real_estate (
                property_id, customer_id, property_name, location, value_sgd, loan_sgd,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"PROP-{customer_id}-{slugify(property.get('property', 'property'))}",
                customer_id,
                property.get("property"),
                property.get("location"),
                property.get("value_sgd"),
                property.get("loan_sgd"),
                timestamp,
                timestamp,
            ),
        )

    for card in profile.get("credit", {}).get("credit_cards", []):
        limit_value, currency = value_and_currency(card, ["limit_usd", "limit_sgd", "credit_limit_usd", "credit_limit_sgd"])
        outstanding_value, _ = value_and_currency(card, ["outstanding_usd", "outstanding_sgd", "outstanding_balance_usd"])
        cursor.execute(
            """
            INSERT INTO cards (
                card_id, customer_id, account_id, card_type, card_name, card_number_masked,
                status, credit_limit_usd, outstanding_balance_usd, annual_fee_usd,
                renewal_date, expiry_date, issued_date, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"CRD-{customer_id}-{slugify(card.get('product', 'card'))}",
                customer_id,
                None,
                card.get("product"),
                card.get("product"),
                "****",
                card.get("status"),
                limit_value,
                outstanding_value,
                None,
                None,
                None,
                None,
                timestamp,
            ),
        )


def insert_portfolio(cursor: sqlite3.Cursor, profile: dict[str, Any]) -> None:
    customer_id = profile["profile"]["customer_id"]
    timestamp = now_ts()
    portfolio = profile.get("portfolio", {})
    allocation = portfolio.get("allocation", {})
    risk_metrics = portfolio.get("risk_metrics", {})

    def pct_for(*names: str) -> float | None:
        total = 0.0
        found = False
        for name in names:
            if name in allocation:
                total += float(allocation[name].get("pct") or 0)
                found = True
        return round(total, 2) if found else None

    equities = pct_for("Public Equities", "Equities")
    fixed_income = pct_for("Fixed Income")
    private_equity = pct_for("Private Equity")
    hedge_funds = pct_for("Hedge Funds")
    real_assets = pct_for("Real Asset Funds", "Real Assets & Cash")
    structured = pct_for("Structured Products")
    cash = pct_for("Cash within Portfolio", "Cash")

    cursor.execute(
        """
        INSERT INTO portfolio_allocations (
            allocation_id, customer_id, snapshot_date, equities_percent, fixed_income_percent,
            private_equity_percent, hedge_funds_percent, real_assets_cash_percent,
            commodities_percent, crypto_percent, structured_products_percent,
            cash_percent, other_percent, total_portfolio_value_usd, ytd_performance_percent,
            one_year_performance_percent, sharpe_ratio, volatility_pct, benchmark_name, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            f"PAL-{customer_id}-{slugify(portfolio.get('last_updated', 'snapshot'))}",
            customer_id,
            portfolio.get("last_updated"),
            equities,
            fixed_income,
            private_equity,
            hedge_funds,
            real_assets,
            None,
            None,
            structured,
            cash,
            None,
            first_non_null(portfolio.get("total_value_usd"), portfolio.get("total_value_sgd")),
            portfolio.get("ytd_return_pct"),
            portfolio.get("one_year_return_pct"),
            risk_metrics.get("sharpe_ratio"),
            risk_metrics.get("volatility_pct"),
            portfolio.get("benchmark") or "MSCI World",
            timestamp,
        ),
    )


def insert_portfolio_timeseries(cursor: sqlite3.Cursor, profile: dict[str, Any]) -> None:
    customer_id = profile["profile"]["customer_id"]
    timestamp = now_ts()
    portfolio = profile.get("portfolio", {})

    for index, point in enumerate(portfolio.get("portfolio_history", []), start=1):
        month_label = str(point.get("month") or "")
        year_num, month_num = parse_month_label(month_label)
        value = first_non_null(point.get("value_usd"), point.get("value_sgd"), point.get("value"), default=0.0)
        cursor.execute(
            """
            INSERT INTO portfolio_history (
                history_id, customer_id, year, month, month_label, portfolio_value_usd, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"PHS-{customer_id}-{index}",
                customer_id,
                year_num,
                month_num,
                month_label,
                float(value),
                timestamp,
            ),
        )

    for index, point in enumerate(portfolio.get("monthly_returns", []), start=1):
        month_label = str(point.get("month") or "")
        year_num, month_num = parse_month_label(month_label)
        cursor.execute(
            """
            INSERT INTO monthly_returns (
                return_id, customer_id, year, month, month_label, return_pct, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"MRT-{customer_id}-{index}",
                customer_id,
                year_num,
                month_num,
                month_label,
                float(point.get("value") or 0),
                timestamp,
            ),
        )

    for index, point in enumerate(portfolio.get("benchmark_comparison", []), start=1):
        month_label = str(point.get("month") or "")
        year_num, month_num = parse_month_label(month_label)
        portfolio_value = first_non_null(point.get("portfolio"), point.get("value"), default=0.0)
        benchmark_value = first_non_null(point.get("benchmark"), point.get("value"), default=0.0)
        cursor.execute(
            """
            INSERT INTO benchmark_comparison (
                benchmark_id, customer_id, year, month, month_label,
                portfolio_return_pct, benchmark_return_pct, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"BMC-{customer_id}-{index}",
                customer_id,
                year_num,
                month_num,
                month_label,
                float(portfolio_value),
                float(benchmark_value),
                timestamp,
            ),
        )


def insert_transactions(cursor: sqlite3.Cursor, profile: dict[str, Any]) -> None:
    customer_id = profile["profile"]["customer_id"]
    timestamp = now_ts()
    accounts = profile.get("accounts", [])
    default_account = accounts[0]["account_id"] if accounts else None

    for index, txn in enumerate(profile.get("recent_transactions", []), start=1):
        amount = float(first_non_null(txn.get("amount_usd"), txn.get("amount"), default=0.0))
        currency = txn.get("currency") or "USD"
        txn_date = txn.get("transaction_date") or txn.get("date")
        cursor.execute(
            """
            INSERT INTO transactions (
                transaction_id, account_id, customer_id, transaction_date, amount_usd,
                currency, description, type, merchant, category, status, dispute_reason,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"TXN-{customer_id}-{slugify(str(txn_date or index))}-{index}",
                txn.get("account") or default_account,
                customer_id,
                txn_date,
                amount,
                currency,
                txn.get("description"),
                txn.get("type") or ("Credit" if amount >= 0 else "Debit"),
                txn.get("merchant"),
                txn.get("category"),
                txn.get("status") or "Completed",
                txn.get("dispute_reason"),
                timestamp,
            ),
        )


def insert_insights_signals(cursor: sqlite3.Cursor, profile: dict[str, Any]) -> None:
    customer_id = profile["profile"]["customer_id"]
    timestamp = now_ts()

    for index, signal in enumerate(profile.get("insights_signals", []), start=1):
        signal_id = str(signal.get("id") or f"INS-{customer_id}-{index}")
        cursor.execute(
            """
            INSERT INTO insights_signals (
                signal_id, customer_id, priority, category, icon, title, trigger, summary,
                suggested_actions_json, rm_context, tags_json, display_order, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                signal_id,
                customer_id,
                signal.get("priority"),
                signal.get("category"),
                signal.get("icon"),
                signal.get("title"),
                signal.get("trigger"),
                signal.get("summary"),
                json.dumps(signal.get("suggested_actions") or []),
                signal.get("rm_context"),
                json.dumps(signal.get("tags") or []),
                index,
                timestamp,
                timestamp,
            ),
        )


def insert_applications(cursor: sqlite3.Cursor, profile: dict[str, Any]) -> None:
    customer_id = profile["profile"]["customer_id"]
    timestamp = now_ts()
    for index, app in enumerate(profile.get("applications", []), start=1):
        app_id = str(app.get("application_id") or app.get("id") or f"APP-{customer_id}-{index}")
        cursor.execute(
            """
            INSERT INTO applications (
                application_id, customer_id, application_type, product_name, status,
                amount_or_limit_usd, submitted_date, expected_completion_date, notes,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                app_id,
                customer_id,
                app.get("application_type") or app.get("type"),
                app.get("product_name") or app.get("product"),
                app.get("status"),
                first_non_null(app.get("amount_or_limit_usd"), app.get("amount_or_limit")),
                app.get("submitted_date") or app.get("date"),
                app.get("expected_completion_date") or app.get("expected_completion"),
                app.get("notes"),
                timestamp,
                timestamp,
            ),
        )


def insert_appointments(cursor: sqlite3.Cursor, profile: dict[str, Any]) -> None:
    customer_id = profile["profile"]["customer_id"]
    timestamp = now_ts()
    for index, appointment in enumerate(profile.get("appointments", []), start=1):
        appointment_id = str(appointment.get("appointment_id") or appointment.get("id") or f"APT-{customer_id}-{index}")
        scheduled_datetime = appointment.get("scheduled_datetime")
        if not scheduled_datetime and appointment.get("date") and appointment.get("time"):
            scheduled_datetime = f"{appointment['date']}T{appointment['time']}"
        cursor.execute(
            """
            INSERT INTO appointments (
                appointment_id, customer_id, relationship_manager_id, appointment_type,
                scheduled_datetime, duration_minutes, location, status, notes,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                appointment_id,
                customer_id,
                appointment.get("relationship_manager_id") or appointment.get("rm"),
                appointment.get("appointment_type") or appointment.get("type"),
                scheduled_datetime,
                appointment.get("duration_minutes"),
                appointment.get("location"),
                appointment.get("status"),
                appointment.get("notes"),
                timestamp,
                timestamp,
            ),
        )


def insert_kyc(cursor: sqlite3.Cursor, profile: dict[str, Any]) -> None:
    customer_id = profile["profile"]["customer_id"]
    timestamp = now_ts()
    meta = profile["profile"]
    cursor.execute(
        """
        INSERT INTO kyc_reviews (
            customer_id, kyc_status, last_reviewed, next_due_date, documents_required,
            document_status, notes, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            customer_id,
            meta.get("kyc_status"),
            meta.get("kyc_last_reviewed"),
            None,
            None,
            "All_Submitted",
            None,
            timestamp,
            timestamp,
        ),
    )


def rebuild_database() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    profiles = [load_profile(path) for path in KEEP_FILES]

    with sqlite3.connect(DB_PATH) as connection:
        connection.executescript(SCHEMA_SQL)
        cursor = connection.cursor()

        for profile in profiles:
            insert_customer_rows(cursor, profile)
            insert_accounts(cursor, profile)
            insert_holdings(cursor, profile)
            insert_credit(cursor, profile)
            insert_portfolio(cursor, profile)
            insert_portfolio_timeseries(cursor, profile)
            insert_insights_signals(cursor, profile)
            insert_transactions(cursor, profile)
            insert_applications(cursor, profile)
            insert_appointments(cursor, profile)
            insert_kyc(cursor, profile)

        connection.commit()

    print(f"Seeded {len(profiles)} customers into {DB_PATH}")


if __name__ == "__main__":
    rebuild_database()
