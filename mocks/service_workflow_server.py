"""
mocks/service_workflow_server.py (Port 9003)

Specialist Agent: Client Services & FX Treasury.
Responsibilities: Appointments, escalations, FX rates, currency hedging.
"""

from fastapi import FastAPI, HTTPException, Header
from base import db

app = FastAPI(title="UBS Service Workflow MCP (9003)")

def get_auth_customer(authorization: str):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token")
    cid = authorization.removeprefix("Bearer ").strip()
    customer = db.get_customer(cid)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer

@app.get("/appointments")
def get_appointments(authorization: str = Header(...)):
    customer = get_auth_customer(authorization)
    return {"appointments": customer.get("appointments", [])}

@app.get("/fx-rates")
def get_fx_rates():
    # Mock data matches original mock_api/main.py
    return {
        "base_currency": "USD",
        "rates": {
            "SGD": 1.354, "EUR": 0.924, "GBP": 0.792, "CHF": 0.901,
            "JPY": 149.82, "AUD": 1.552, "CNH": 7.241
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9003)
