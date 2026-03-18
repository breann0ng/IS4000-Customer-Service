"""
mock_api_router.py

FastAPI router exposing stub UBS private banking API endpoints.
Mount this on your main FastAPI app.

All data is served from seed_data.py (in-memory).
Auth: pass  Authorization: Bearer <customer_id>  e.g. Bearer C-001

Endpoints:
  GET  /api/mock/customers/me                  — authenticated customer profile
  GET  /api/mock/customers/{customer_id}       — customer profile (RM use)
  GET  /api/mock/accounts                      — all accounts for auth'd customer
  GET  /api/mock/accounts/{account_id}         — single account detail
  GET  /api/mock/accounts/{account_id}/transactions — transaction history
  GET  /api/mock/portfolio                     — portfolio summary
  GET  /api/mock/portfolio/holdings            — detailed holdings
  GET  /api/mock/credit                        — credit products overview
  GET  /api/mock/real-estate                   — property holdings
  GET  /api/mock/appointments                  — upcoming appointments
  POST /api/mock/appointments                  — book new appointment
  GET  /api/mock/notifications                 — unread notifications
  POST /api/mock/notifications/{id}/read       — mark notification read
  GET  /api/mock/fx-rates                      — live-ish mock FX rates
  GET  /api/mock/health                        — health check
"""

from __future__ import annotations

from datetime import datetime, timezone, date
from typing import Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Header, Query
from pydantic import BaseModel

from mock_db import CUSTOMERS, get_customer, search_customers

router = APIRouter(prefix="/api/mock", tags=["Mock Banking API"])


# ── Auth helper ───────────────────────────────────────────────────────────────

def get_current_customer(authorization: str = Header(...)) -> dict:
    """
    Minimal mock auth. Expects:  Authorization: Bearer C-001
    Returns the full customer data dict.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization format. Use: Bearer <customer_id>")

    customer_id = authorization.removeprefix("Bearer ").strip()
    customer = get_customer(customer_id)

    if not customer:
        raise HTTPException(
            status_code=401,
            detail=f"Customer '{customer_id}' not found. Valid IDs: {list(CUSTOMERS.keys())}"
        )
    return customer


# ── Request / Response models ─────────────────────────────────────────────────

class AppointmentRequest(BaseModel):
    appointment_type: str          # e.g. "Portfolio Review"
    preferred_date: str            # YYYY-MM-DD
    preferred_time: str            # HH:MM
    location_preference: str       # "In-person" | "Video call" | "Phone"
    notes: Optional[str] = None


class AppointmentResponse(BaseModel):
    appointment_id: str
    status: str
    message: str
    confirmed_date: str
    confirmed_time: str
    rm_name: str
    location: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/health")
def health_check():
    return {"status": "ok", "service": "UBS Mock Banking API", "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get("/customers/me")
def get_my_profile(customer: dict = Depends(get_current_customer)):
    """Return the authenticated customer's profile."""
    return {
        "customer_id": customer["profile"]["customer_id"],
        "full_name": customer["profile"]["full_name"],
        "preferred_name": customer["profile"]["preferred_name"],
        "segment": customer["profile"]["segment"],
        "tier": customer["profile"]["tier"],
        "relationship_manager": customer["profile"]["relationship_manager"],
        "rm_email": customer["profile"]["rm_email"],
        "rm_phone": customer["profile"]["rm_phone"],
        "risk_profile": customer["profile"]["risk_profile"],
        "kyc_status": customer["profile"]["kyc_status"],
        "aum_with_ubs_usd": customer["profile"]["aum_with_ubs_usd"],
        "preferred_contact": customer["profile"]["preferred_contact"],
        "notifications_unread": sum(1 for n in customer.get("notifications", []) if not n["read"]),
    }


@router.get("/customers/search")
def search_customer_by_name(name: str = Query(..., description="Customer name to search"), customer: dict = Depends(get_current_customer)):
    """Search customers by name. (RM access in real system — demo allows any auth'd user.)"""
    results = search_customers(name)
    return {"results": results, "count": len(results)}


@router.get("/accounts")
def list_accounts(customer: dict = Depends(get_current_customer)):
    """List all accounts for the authenticated customer."""
    accounts = customer.get("accounts", [])
    return {
        "customer_id": customer["profile"]["customer_id"],
        "accounts": accounts,
        "total_accounts": len(accounts),
    }


@router.get("/accounts/{account_id}")
def get_account(account_id: str, customer: dict = Depends(get_current_customer)):
    """Get details for a specific account."""
    accounts = customer.get("accounts", [])
    account = next((a for a in accounts if a["account_id"] == account_id), None)
    if not account:
        raise HTTPException(status_code=404, detail=f"Account '{account_id}' not found for this customer.")
    return account


@router.get("/accounts/{account_id}/transactions")
def get_transactions(
    account_id: str,
    limit: int = Query(10, ge=1, le=50),
    customer: dict = Depends(get_current_customer),
):
    """Get recent transactions for an account."""
    accounts = customer.get("accounts", [])
    account = next((a for a in accounts if a["account_id"] == account_id), None)
    if not account:
        raise HTTPException(status_code=404, detail=f"Account '{account_id}' not found.")

    # Filter transactions by account
    all_txns = customer.get("recent_transactions", [])
    account_txns = [t for t in all_txns if t.get("account") == account_id]

    # If no account-specific transactions, return general ones (for demo)
    if not account_txns:
        account_txns = all_txns[:limit]

    return {
        "account_id": account_id,
        "transactions": account_txns[:limit],
        "count": len(account_txns[:limit]),
        "note": "Showing most recent transactions",
    }


@router.get("/transactions")
def get_all_transactions(
    limit: int = Query(10, ge=1, le=50),
    customer: dict = Depends(get_current_customer),
):
    """Get recent transactions across all accounts."""
    txns = customer.get("recent_transactions", [])
    return {
        "transactions": txns[:limit],
        "count": len(txns[:limit]),
        "total_available": len(txns),
    }


@router.get("/portfolio")
def get_portfolio_summary(customer: dict = Depends(get_current_customer)):
    """Get portfolio summary including allocation and performance."""
    portfolio = customer.get("portfolio", {})
    if not portfolio:
        raise HTTPException(status_code=404, detail="No portfolio found for this customer.")

    return {
        "portfolio_id": portfolio["portfolio_id"],
        "total_value_usd": portfolio["total_value_usd"],
        "currency": portfolio["currency"],
        "mandate_type": portfolio["mandate_type"],
        "allocation": portfolio["allocation"],
        "ytd_return_pct": portfolio.get("ytd_return_pct"),
        "one_year_return_pct": portfolio.get("one_year_return_pct"),
        "last_updated": portfolio["last_updated"],
    }


@router.get("/portfolio/holdings")
def get_portfolio_holdings(customer: dict = Depends(get_current_customer)):
    """Get detailed portfolio holdings including equities, private markets, structured products."""
    portfolio = customer.get("portfolio", {})
    if not portfolio:
        raise HTTPException(status_code=404, detail="No portfolio found.")

    return {
        "portfolio_id": portfolio["portfolio_id"],
        "total_value_usd": portfolio["total_value_usd"],
        "top_equity_holdings": portfolio.get("top_equity_holdings", []),
        "private_markets": portfolio.get("private_markets", []),
        "structured_products": portfolio.get("structured_products", []),
    }


@router.get("/credit")
def get_credit_summary(customer: dict = Depends(get_current_customer)):
    """Get credit products overview: Lombard facility, mortgages, credit cards."""
    credit = customer.get("credit", {})
    return {
        "customer_id": customer["profile"]["customer_id"],
        "credit_products": credit,
        "summary": {
            "has_lombard": "lombard_facility" in credit,
            "has_mortgage": "mortgage" in credit,
            "credit_cards_count": len(credit.get("credit_cards", [])),
        },
    }


@router.get("/real-estate")
def get_real_estate(customer: dict = Depends(get_current_customer)):
    """Get real estate holdings."""
    properties = customer.get("real_estate", [])
    return {
        "customer_id": customer["profile"]["customer_id"],
        "properties": properties,
        "count": len(properties),
    }


@router.get("/appointments")
def get_appointments(customer: dict = Depends(get_current_customer)):
    """Get upcoming appointments."""
    appointments = customer.get("appointments", [])
    upcoming = [a for a in appointments if a["status"] in ("Confirmed", "Tentative")]
    return {
        "appointments": upcoming,
        "count": len(upcoming),
    }


@router.post("/appointments", response_model=AppointmentResponse)
def book_appointment(
    request: AppointmentRequest,
    customer: dict = Depends(get_current_customer),
):
    """Book a new appointment with the relationship manager."""
    rm_name = customer["profile"]["relationship_manager"]

    # Simple mock logic: confirm most requests, flag weekends
    try:
        req_date = date.fromisoformat(request.preferred_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    is_weekend = req_date.weekday() >= 5
    if is_weekend:
        raise HTTPException(
            status_code=422,
            detail=f"{request.preferred_date} falls on a weekend. Please choose a weekday."
        )

    location_map = {
        "In-person": "UBS Singapore, One Raffles Quay, North Tower",
        "Video call": "UBS Secure Video — link will be sent 30 min before",
        "Phone": f"Your RM {rm_name} will call your registered mobile",
    }
    location = location_map.get(request.location_preference, request.location_preference)

    return AppointmentResponse(
        appointment_id=f"APT-NEW-{uuid.uuid4().hex[:6].upper()}",
        status="Confirmed",
        message=f"Your {request.appointment_type} has been booked with {rm_name}.",
        confirmed_date=request.preferred_date,
        confirmed_time=request.preferred_time,
        rm_name=rm_name,
        location=location,
    )


@router.get("/notifications")
def get_notifications(
    unread_only: bool = Query(False),
    customer: dict = Depends(get_current_customer),
):
    """Get notifications for the customer."""
    notifications = customer.get("notifications", [])
    if unread_only:
        notifications = [n for n in notifications if not n["read"]]
    return {
        "notifications": notifications,
        "unread_count": sum(1 for n in notifications if not n["read"]),
    }


@router.post("/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: str,
    customer: dict = Depends(get_current_customer),
):
    """Mark a notification as read."""
    notifications = customer.get("notifications", [])
    notif = next((n for n in notifications if n["id"] == notification_id), None)
    if not notif:
        raise HTTPException(status_code=404, detail=f"Notification '{notification_id}' not found.")
    notif["read"] = True
    return {"notification_id": notification_id, "status": "marked_read"}


@router.get("/fx-rates")
def get_fx_rates(customer: dict = Depends(get_current_customer)):
    """
    Return mock FX rates. In production this would call a live rates feed.
    Rates are indicative only — realistic as of early 2026.
    """
    return {
        "base_currency": "USD",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "rates": {
            "SGD": 1.354,
            "EUR": 0.924,
            "GBP": 0.792,
            "CHF": 0.901,
            "JPY": 149.82,
            "AUD": 1.552,
            "DKK": 6.882,
            "CNH": 7.241,
        },
        "note": "Indicative rates for demo purposes. Not for transaction use.",
    }


@router.get("/net-worth-summary")
def get_net_worth_summary(customer: dict = Depends(get_current_customer)):
    """High-level net worth breakdown."""
    profile = customer["profile"]
    portfolio = customer.get("portfolio", {})
    accounts = customer.get("accounts", [])
    credit = customer.get("credit", {})
    real_estate = customer.get("real_estate", [])

    # Approximate liquid cash from accounts
    liquid_cash = sum(
        a.get("balance", a.get("total_usd_equivalent", 0))
        for a in accounts
    )

    return {
        "customer_id": profile["customer_id"],
        "full_name": profile["full_name"],
        "estimated_net_worth_usd": profile["net_worth_usd"],
        "aum_with_ubs_usd": profile["aum_with_ubs_usd"],
        "breakdown": {
            "investment_portfolio_usd": portfolio.get("total_value_usd", 0),
            "liquid_cash_approx_usd": round(liquid_cash),
            "real_estate_properties": len(real_estate),
        },
        "credit_summary": {
            "lombard_drawn_usd": credit.get("lombard_facility", {}).get("drawn_usd", 0),
            "mortgage_outstanding": credit.get("mortgage", {}).get("outstanding_sgd", 0),
        },
        "segment": profile["segment"],
        "risk_profile": profile["risk_profile"],
    }
