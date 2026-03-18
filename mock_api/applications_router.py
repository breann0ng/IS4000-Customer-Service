"""
applications_router.py

Stub API for customer application and case status tracking.
Covers any in-flight request a private banking client might have:
  - New account or product applications
  - Mortgage / Lombard applications or limit increases
  - KYC / document reviews
  - Service requests (card replacement, address change, etc.)
  - Investment mandate changes

Each customer's open applications live in their JSON file
under the "applications" key.

Endpoints:
  GET  /api/applications                    — all applications for auth'd customer
  GET  /api/applications/{application_id}   — single application detail
  POST /api/applications                    — submit a new service request
  GET  /api/applications/types              — list of requestable application types
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel

from mock_db import get_customer

router = APIRouter(prefix="/api/applications", tags=["Applications & Case Status"])


# ── Auth ──────────────────────────────────────────────────────────────────────

def get_current_customer(authorization: str = Header(...)) -> dict:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Use: Authorization: Bearer <customer_id>")
    customer_id = authorization.removeprefix("Bearer ").strip()
    customer = get_customer(customer_id)
    if not customer:
        raise HTTPException(status_code=401, detail=f"Customer '{customer_id}' not found.")
    return customer


# ── Models ────────────────────────────────────────────────────────────────────

class NewApplicationRequest(BaseModel):
    application_type: str       # must be one of APPLICATION_TYPES keys
    description: str            # free text — what the client is requesting
    priority: Optional[str] = "Normal"   # Normal | Urgent


class NewApplicationResponse(BaseModel):
    application_id: str
    application_type: str
    status: str
    submitted_at: str
    estimated_completion: str
    assigned_to: str
    message: str


# ── Application type catalogue ────────────────────────────────────────────────

APPLICATION_TYPES = {
    "account_opening":          {"label": "New Account Opening",             "typical_days": 3,  "team": "Account Services"},
    "lombard_increase":         {"label": "Lombard Facility Limit Increase", "typical_days": 5,  "team": "Credit Team"},
    "lombard_new":              {"label": "New Lombard Credit Facility",     "typical_days": 7,  "team": "Credit Team"},
    "mortgage_application":     {"label": "New Mortgage Application",        "typical_days": 14, "team": "Mortgage Team"},
    "mortgage_refinance":       {"label": "Mortgage Refinancing",            "typical_days": 10, "team": "Mortgage Team"},
    "mortgage_rate_review":     {"label": "Mortgage Rate Review",            "typical_days": 5,  "team": "Mortgage Team"},
    "kyc_update":               {"label": "KYC Document Update",             "typical_days": 3,  "team": "Compliance"},
    "card_replacement":         {"label": "Card Replacement",                "typical_days": 2,  "team": "Card Services"},
    "card_limit_increase":      {"label": "Credit Card Limit Increase",      "typical_days": 3,  "team": "Card Services"},
    "address_change":           {"label": "Address / Contact Detail Change", "typical_days": 1,  "team": "Account Services"},
    "mandate_change":           {"label": "Investment Mandate Change",       "typical_days": 3,  "team": "Investment Services"},
    "beneficiary_update":       {"label": "Beneficiary Account Update",      "typical_days": 2,  "team": "Account Services"},
    "account_closure":          {"label": "Account Closure Request",         "typical_days": 5,  "team": "Account Services"},
    "fx_forward_booking":       {"label": "FX Forward Booking",              "typical_days": 1,  "team": "FX Desk"},
    "structured_product_query": {"label": "Structured Product Enquiry",      "typical_days": 2,  "team": "Investment Services"},
    "general_service_request":  {"label": "General Service Request",         "typical_days": 2,  "team": "Client Services"},
}

# Status progression for display
STATUS_DESCRIPTIONS = {
    "Submitted":           "Your request has been received and logged.",
    "Under Review":        "Our team is reviewing your request. No action needed from you yet.",
    "Pending Documents":   "We need additional documents from you. Your RM will be in touch.",
    "Pending Approval":    "Your request is awaiting internal approval. Typically 1–2 business days.",
    "Approved":            "Your request has been approved. Processing is underway.",
    "In Progress":         "Your request is actively being processed.",
    "Completed":           "Your request has been completed successfully.",
    "On Hold":             "Your request is on hold. Please contact your RM for details.",
    "Cancelled":           "This request has been cancelled.",
    "Rejected":            "Unfortunately this request could not be approved. Please contact your RM.",
}


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/types")
def get_application_types():
    """List all requestable application and service request types."""
    return {
        "application_types": [
            {
                "type_id": k,
                "label": v["label"],
                "typical_processing_days": v["typical_days"],
                "handled_by": v["team"],
            }
            for k, v in APPLICATION_TYPES.items()
        ],
        "count": len(APPLICATION_TYPES),
    }


@router.get("")
def list_applications(
    status: Optional[str] = None,
    customer: dict = Depends(get_current_customer),
):
    """
    List all applications for the authenticated customer.
    Optionally filter by status: ?status=Under+Review
    """
    applications = customer.get("applications", [])

    if status:
        applications = [a for a in applications if a.get("status", "").lower() == status.lower()]

    # Enrich each with status description
    enriched = []
    for app in applications:
        enriched.append({
            **app,
            "status_description": STATUS_DESCRIPTIONS.get(app.get("status", ""), ""),
        })

    open_statuses = {"Submitted", "Under Review", "Pending Documents", "Pending Approval", "In Progress", "On Hold"}
    open_count = sum(1 for a in applications if a.get("status") in open_statuses)

    return {
        "customer_id": customer["profile"]["customer_id"],
        "applications": enriched,
        "total": len(enriched),
        "open": open_count,
        "completed": len(enriched) - open_count,
    }


@router.get("/{application_id}")
def get_application(
    application_id: str,
    customer: dict = Depends(get_current_customer),
):
    """Get full detail for a single application by ID."""
    applications = customer.get("applications", [])
    app = next((a for a in applications if a["application_id"] == application_id), None)

    if not app:
        raise HTTPException(
            status_code=404,
            detail=f"Application '{application_id}' not found for this customer."
        )

    return {
        **app,
        "status_description": STATUS_DESCRIPTIONS.get(app.get("status", ""), ""),
        "next_steps": _get_next_steps(app),
    }


@router.post("", response_model=NewApplicationResponse)
def submit_application(
    request: NewApplicationRequest,
    customer: dict = Depends(get_current_customer),
):
    """Submit a new service request or application."""
    app_type = APPLICATION_TYPES.get(request.application_type)
    if not app_type:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown application type '{request.application_type}'. "
                   f"Call GET /api/applications/types for valid options."
        )

    # Block account_closure in demo (matches MVP non-goals from proposal)
    if request.application_type == "account_closure":
        raise HTTPException(
            status_code=422,
            detail="Account closure requests must be handled directly with your Relationship Manager."
        )

    now = datetime.now(timezone.utc)
    app_id = f"APP-{uuid.uuid4().hex[:8].upper()}"
    rm_name = customer["profile"]["relationship_manager"]

    # Estimate completion (skip weekends roughly)
    days = app_type["typical_days"]
    estimated = f"Within {days} business day{'s' if days > 1 else ''}"

    return NewApplicationResponse(
        application_id=app_id,
        application_type=app_type["label"],
        status="Submitted",
        submitted_at=now.isoformat(),
        estimated_completion=estimated,
        assigned_to=f"{app_type['team']} (cc: {rm_name})",
        message=(
            f"Your {app_type['label']} request (ref: {app_id}) has been submitted. "
            f"Expected completion: {estimated}. "
            f"Your RM {rm_name} will be in touch if further information is needed."
        ),
    )


def _get_next_steps(app: dict) -> str:
    """Return a plain-English next-steps string based on current status."""
    status = app.get("status", "")
    mapping = {
        "Submitted":         "No action needed. You will receive an update within 1 business day.",
        "Under Review":      "Our team is reviewing your case. You will be contacted if documents are needed.",
        "Pending Documents": f"Please provide the requested documents to your RM: {app.get('documents_required', 'see RM instructions')}",
        "Pending Approval":  "Awaiting internal sign-off. No action required from you.",
        "Approved":          "Processing has begun. You will be notified when complete.",
        "In Progress":       "Actively being processed. Expected completion: " + app.get("expected_completion", "see RM"),
        "Completed":         "This request is complete. Contact your RM if you have questions.",
        "On Hold":           "Please contact your RM to resolve the hold on this application.",
        "Cancelled":         "This request was cancelled. Submit a new request if needed.",
        "Rejected":          "Please contact your RM to discuss alternatives.",
    }
    return mapping.get(status, "Contact your RM for an update.")
