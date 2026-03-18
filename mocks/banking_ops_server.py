"""
mocks/banking_ops_server.py (Port 9001)

Specialist Agent: Wealth Advisory, Lending & Credit.
Responsibilities: Portfolio performance, investment strategy, Lombard lending, mortgages.
"""

from fastapi import FastAPI, HTTPException, Header
from base import db

app = FastAPI(title="UBS Banking Ops MCP (9001)")

def get_auth_customer(authorization: str):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token")
    cid = authorization.removeprefix("Bearer ").strip()
    customer = db.get_customer(cid)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer

@app.get("/portfolio")
def get_portfolio(authorization: str = Header(...)):
    customer = get_auth_customer(authorization)
    return customer.get("portfolio", {})

@app.get("/credit")
def get_credit(authorization: str = Header(...)):
    customer = get_auth_customer(authorization)
    return customer.get("credit", {})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9001)
