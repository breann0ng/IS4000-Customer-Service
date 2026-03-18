"""
mocks/knowledge_server.py (Port 9002)

Specialist Agent: Private Banking, Compliance & Tax.
Responsibilities: Account operations, fund transfers, regulatory updates, RAG retrieval.
"""

from fastapi import FastAPI, HTTPException, Header
from base import db

app = FastAPI(title="UBS Knowledge & Private Banking MCP (9002)")

def get_auth_customer(authorization: str):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token")
    cid = authorization.removeprefix("Bearer ").strip()
    customer = db.get_customer(cid)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer

@app.get("/accounts")
def list_accounts(authorization: str = Header(...)):
    customer = get_auth_customer(authorization)
    return {
        "accounts": customer.get("accounts", []),
        "total_accounts": len(customer.get("accounts", []))
    }

@app.get("/transactions/{account_id}")
def get_transactions(account_id: str, authorization: str = Header(...)):
    customer = get_auth_customer(authorization)
    txns = customer.get("recent_transactions", [])
    account_txns = [t for t in txns if t.get("account") == account_id]
    return {"transactions": account_txns}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9002)
