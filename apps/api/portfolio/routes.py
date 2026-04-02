import sqlite3
import os
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from apps.api.auth.routes import get_current_user
from apps.api.database.models import User

router = APIRouter(prefix="/portfolio", tags=["portfolio"])

# Root is IS4000-Customer-Service-main/
DB_PATH = Path("data/persona.db").absolute()

def get_db_connection():
    if not DB_PATH.exists():
        raise HTTPException(status_code=500, detail=f"Database not found at {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@router.get("/summary")
async def get_portfolio_summary(current_user: User = Depends(get_current_user)):
    """Return a summary of the current user's portfolio and accounts."""
    username = current_user.username
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get Profile & Portfolio
    cursor.execute('''
        SELECT p.full_name, p.risk_profile, p.aum_usd, pt.equities_pct, pt.fixed_income_pct, pt.cash_pct, pt.ytd_return_pct
        FROM profiles p
        JOIN portfolios pt ON p.customer_id = pt.customer_id
        WHERE p.username = ? OR p.customer_id = ?
    ''', (username, username))
    profile_data = cursor.fetchone()

    if not profile_data:
        conn.close()
        raise HTTPException(status_code=404, detail=f"No portfolio found for user {username}")

    # Get Accounts
    cursor.execute('''
        SELECT a.account_id, a.account_type, a.currency, a.balance 
        FROM accounts a
        JOIN profiles p ON a.customer_id = p.customer_id
        WHERE p.username = ? OR p.customer_id = ?
    ''', (username, username))
    accounts = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return {
        "profile": {
            "full_name": profile_data["full_name"],
            "risk_profile": profile_data["risk_profile"],
            "aum_usd": profile_data["aum_usd"],
        },
        "portfolio": {
            "equities_pct": profile_data["equities_pct"],
            "fixed_income_pct": profile_data["fixed_income_pct"],
            "cash_pct": profile_data["cash_pct"],
            "ytd_return_pct": profile_data["ytd_return_pct"],
        },
        "accounts": accounts
    }

@router.get("/performance")
async def get_portfolio_performance(current_user: User = Depends(get_current_user)):
    """Return monthly performance history for charts."""
    username = current_user.username
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT ph.month, ph.value_usd, ph.return_pct 
        FROM performance_history ph
        JOIN profiles p ON ph.customer_id = p.customer_id
        WHERE p.username = ? OR p.customer_id = ?
        ORDER BY ph.id ASC
    ''', (username, username))
    history = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return history
