"""
rates_router.py

Stub API for current UBS product rates.
These are market-facing rates that change regularly — separate from a
customer's personal account data.

Endpoints:
  GET /api/rates/mortgage          — current mortgage rate tiers
  GET /api/rates/lombard           — Lombard facility base rate
  GET /api/rates/savings           — savings & term deposit rates
  GET /api/rates/cards             — credit card interest rates
  GET /api/rates/fx                — indicative FX spot rates
  GET /api/rates/all               — all rates in one call

All rates are indicative and for demo purposes only.
In production these would be fetched from a live rates feed or treasury system.
"""

from __future__ import annotations

from datetime import datetime, timezone
from fastapi import APIRouter, Depends

from mock_db import get_customer

router = APIRouter(prefix="/api/rates", tags=["Rates API"])

# ── Rate tables (updated manually for demo — in prod these would be live) ────

_AS_OF = "2026-03-18"
_DISCLAIMER = "Indicative rates only. Subject to credit approval and market conditions. Not for transaction use."


MORTGAGE_RATES = {
    "as_of": _AS_OF,
    "currency": "SGD / Multi-currency",
    "disclaimer": _DISCLAIMER,
    "fixed_rate": [
        {"term": "1 year",  "rate_pct": 3.25, "note": "UBS special for AUM > SGD 2M"},
        {"term": "2 years", "rate_pct": 3.45, "note": "Standard fixed"},
        {"term": "3 years", "rate_pct": 3.60, "note": "Standard fixed"},
        {"term": "5 years", "rate_pct": 3.80, "note": "Standard fixed"},
    ],
    "floating_rate": [
        {"benchmark": "SORA 1M",   "spread_pct": 0.80, "effective_rate_pct": 3.98, "note": "Subject to SORA movement"},
        {"benchmark": "SORA 3M",   "spread_pct": 0.75, "effective_rate_pct": 3.95, "note": "Subject to SORA movement"},
    ],
    "private_bank_privilege": {
        "description": "Clients with AUM > SGD 5M may qualify for preferential pricing",
        "discount_bps": 15,
        "contact": "Speak to your Relationship Manager"
    },
    "max_ltv_pct": 75,
    "max_tenure_years": 30,
    "minimum_loan_sgd": 500000,
}

LOMBARD_RATES = {
    "as_of": _AS_OF,
    "disclaimer": _DISCLAIMER,
    "description": "Lombard Credit Facility — credit secured against your investment portfolio",
    "base_rate": {
        "benchmark": "SOFR 1M",
        "current_sofr_pct": 4.32,
        "spread_pct": 0.50,
        "effective_rate_pct": 4.82,
        "note": "Rate subject to SOFR movement and credit review"
    },
    "tiers": [
        {"facility_size_usd": "< 1,000,000",   "spread_pct": 0.75, "effective_rate_pct": 5.07},
        {"facility_size_usd": "1M – 5M",       "spread_pct": 0.55, "effective_rate_pct": 4.87},
        {"facility_size_usd": "5M – 20M",      "spread_pct": 0.45, "effective_rate_pct": 4.77},
        {"facility_size_usd": "> 20M",         "spread_pct": 0.35, "effective_rate_pct": 4.67, "note": "UHNW pricing, subject to RM approval"},
    ],
    "eligible_collateral": [
        "Listed equities (haircut 20–40%)",
        "Investment grade bonds (haircut 10–20%)",
        "UBS managed funds (haircut 15–25%)",
        "Structured products (case by case)",
    ],
    "max_advance_rate_pct": 70,
    "review_frequency": "Annual + triggered by portfolio value changes",
}

SAVINGS_RATES = {
    "as_of": _AS_OF,
    "disclaimer": _DISCLAIMER,
    "savings_accounts": [
        {"product": "Personal Current Account",     "currency": "SGD", "rate_pct": 0.10, "note": "Base rate"},
        {"product": "UBS key4 Savings",             "currency": "SGD", "rate_pct": 2.10, "note": "Digital savings, no minimum"},
        {"product": "Wealth Management Account",    "currency": "USD", "rate_pct": 0.50, "note": "Base rate"},
        {"product": "Wealth Management Account",    "currency": "EUR", "rate_pct": 0.25, "note": "Base rate"},
        {"product": "Wealth Management Account",    "currency": "CHF", "rate_pct": 0.75, "note": "Base rate"},
    ],
    "term_deposits": [
        {"term": "1 month",  "currency": "SGD", "rate_pct": 3.05, "min_amount_sgd": 25000},
        {"term": "3 months", "currency": "SGD", "rate_pct": 3.20, "min_amount_sgd": 25000},
        {"term": "6 months", "currency": "SGD", "rate_pct": 3.35, "min_amount_sgd": 25000},
        {"term": "12 months","currency": "SGD", "rate_pct": 3.40, "min_amount_sgd": 25000},
        {"term": "1 month",  "currency": "USD", "rate_pct": 4.80, "min_amount_usd": 25000},
        {"term": "3 months", "currency": "USD", "rate_pct": 4.95, "min_amount_usd": 25000},
        {"term": "6 months", "currency": "USD", "rate_pct": 4.90, "min_amount_usd": 25000},
        {"term": "12 months","currency": "USD", "rate_pct": 4.75, "min_amount_usd": 25000},
        {"term": "3 months", "currency": "EUR", "rate_pct": 2.80, "min_amount_eur": 25000},
        {"term": "6 months", "currency": "EUR", "rate_pct": 2.95, "min_amount_eur": 25000},
        {"term": "3 months", "currency": "CHF", "rate_pct": 0.80, "min_amount_chf": 25000},
        {"term": "6 months", "currency": "CHF", "rate_pct": 0.90, "min_amount_chf": 25000},
    ],
    "note": "Private banking clients with AUM > USD 2M may qualify for enhanced rates. Contact your RM."
}

CARD_RATES = {
    "as_of": _AS_OF,
    "disclaimer": _DISCLAIMER,
    "credit_cards": [
        {
            "product": "UBS Visa Infinite",
            "annual_fee_sgd": 588,
            "purchase_rate_pct": 28.0,
            "cash_advance_rate_pct": 28.0,
            "interest_free_days": 25,
            "minimum_payment_pct": 1.0,
            "late_payment_fee_sgd": 100,
            "note": "Annual fee waived for clients with AUM > SGD 500K"
        },
        {
            "product": "UBS Mastercard World Elite",
            "annual_fee_sgd": 540,
            "purchase_rate_pct": 28.0,
            "cash_advance_rate_pct": 28.0,
            "interest_free_days": 25,
            "minimum_payment_pct": 1.0,
            "late_payment_fee_sgd": 100,
            "note": "Annual fee waived for clients with AUM > SGD 500K"
        },
        {
            "product": "UBS Visa Gold",
            "annual_fee_chf": 100,
            "purchase_rate_pct": 14.4,
            "cash_advance_rate_pct": 14.4,
            "interest_free_days": 30,
            "note": "Switzerland product"
        },
        {
            "product": "UBS Visa Platinum",
            "annual_fee_sgd": 192,
            "purchase_rate_pct": 26.9,
            "cash_advance_rate_pct": 26.9,
            "interest_free_days": 25,
            "note": "Entry-level card for Affluent segment"
        },
    ]
}

FX_SPOT_RATES = {
    "as_of": datetime.now(timezone.utc).isoformat(),
    "base_currency": "USD",
    "disclaimer": _DISCLAIMER,
    "rates": {
        "SGD": {"mid": 1.3540, "buy": 1.3520, "sell": 1.3560},
        "EUR": {"mid": 0.9240, "buy": 0.9225, "sell": 0.9255},
        "GBP": {"mid": 0.7920, "buy": 0.7905, "sell": 0.7935},
        "CHF": {"mid": 0.9010, "buy": 0.8995, "sell": 0.9025},
        "JPY": {"mid": 149.82,"buy": 149.50, "sell": 150.14},
        "AUD": {"mid": 1.5520, "buy": 1.5495, "sell": 1.5545},
        "DKK": {"mid": 6.8820, "buy": 6.8700, "sell": 6.8940},
        "SEK": {"mid": 10.420, "buy": 10.400, "sell": 10.440},
        "CNH": {"mid": 7.2410, "buy": 7.2300, "sell": 7.2520},
        "INR": {"mid": 83.420, "buy": 83.280, "sell": 83.560},
        "HKD": {"mid": 7.7780, "buy": 7.7720, "sell": 7.7840},
        "CAD": {"mid": 1.3680, "buy": 1.3660, "sell": 1.3700},
    },
    "cross_rates": {
        "EUR/SGD": {"mid": 1.4656, "buy": 1.4630, "sell": 1.4682},
        "GBP/SGD": {"mid": 1.7099, "buy": 1.7065, "sell": 1.7133},
        "AUD/SGD": {"mid": 0.8724, "buy": 0.8706, "sell": 0.8742},
        "EUR/CHF": {"mid": 0.9752, "buy": 0.9735, "sell": 0.9769},
        "GBP/EUR": {"mid": 1.1688, "buy": 1.1665, "sell": 1.1711},
    },
    "note": "Rates update every 15 minutes during market hours. Actual transaction rates may differ."
}


# ── Endpoints ─────────────────────────────────────────────────────────────────

def _auth(authorization: str = "") -> dict | None:
    """Optional auth — rates are accessible to any authenticated customer."""
    from fastapi import Header
    return None


@router.get("/mortgage")
def get_mortgage_rates():
    """Current UBS mortgage rate tiers for new applications."""
    return MORTGAGE_RATES


@router.get("/lombard")
def get_lombard_rates():
    """Current Lombard credit facility rates by facility size."""
    return LOMBARD_RATES


@router.get("/savings")
def get_savings_rates():
    """Current savings account and term deposit rates by currency and tenor."""
    return SAVINGS_RATES


@router.get("/cards")
def get_card_rates():
    """Credit card interest rates, fees, and conditions."""
    return CARD_RATES


@router.get("/fx")
def get_fx_rates():
    """Indicative FX spot rates — mid, buy, and sell for major currency pairs."""
    return FX_SPOT_RATES


@router.get("/all")
def get_all_rates():
    """All current rates in a single call."""
    return {
        "as_of": _AS_OF,
        "mortgage": MORTGAGE_RATES,
        "lombard": LOMBARD_RATES,
        "savings": SAVINGS_RATES,
        "cards": CARD_RATES,
        "fx": FX_SPOT_RATES,
    }
