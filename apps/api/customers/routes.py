"""Customer data API routes for profile and performance retrieval."""

from fastapi import APIRouter, Depends, HTTPException, status

from apps.api.auth.routes import get_current_user
from apps.api.customers.customer_data_client import get_customer_bundle
from apps.api.customers.data_service import DataService
from apps.api.database.models import User
from apps.api.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("/me/performance")
async def get_my_performance(current_user: User = Depends(get_current_user)) -> dict:
    """Return performance data for the currently authenticated user's customer profile.

    Returns:
        A dictionary containing portfolio history, allocation, and returns.
    """
    if not current_user.customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not mapped to a customer profile",
        )

    bundle = await get_customer_bundle(current_user.customer_id)
    data = DataService.get_customer_performance_from_bundle(current_user.customer_id, bundle)
    if not data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Data for customer {current_user.customer_id} not found",
        )

    return data


@router.get("/me/summary")
async def get_my_summary(current_user: User = Depends(get_current_user)) -> dict:
    """Return a high-level summary of the customer's profile and accounts."""
    if not current_user.customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not mapped to a customer profile",
        )

    bundle = await get_customer_bundle(current_user.customer_id)
    data = DataService.get_customer_summary_from_bundle(bundle)
    if not data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Data for customer {current_user.customer_id} not found",
        )

    return data
