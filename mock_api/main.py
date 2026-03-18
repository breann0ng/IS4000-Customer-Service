"""
main.py

FastAPI application entry point.
Mounts the mock banking API router for demo/testing.

Run:
    uvicorn main:app --reload --port 8080

Then visit:
    http://localhost:8080/docs   ← Swagger UI with all endpoints
    http://localhost:8080/redoc  ← ReDoc UI
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from mock_api_router import router as mock_router
from rates_router import router as rates_router
from applications_router import router as applications_router
from mock_db import CUSTOMERS

app = FastAPI(
    title="UBS Private Banking — Mock API",
    description=f"""
Demo stub API for the UBS Private Banking chatbot.

## Authentication
All endpoints require:  `Authorization: Bearer <customer_id>`

## Demo Customer IDs
Available IDs: {", ".join(sorted(CUSTOMERS.keys()))}

## Routers
| Prefix | Purpose |
|--------|---------|
| `/api/mock/` | Personal banking data — accounts, portfolio, credit, appointments |
| `/api/rates/` | Market rates — mortgage, Lombard, savings, FX |
| `/api/applications/` | Application & case status tracking |
    """,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(mock_router)
app.include_router(rates_router)
app.include_router(applications_router)


@app.get("/")
def root():
    return {
        "service": "UBS Mock Banking API",
        "docs": "/docs",
        "health": "/api/mock/health",
        "demo_customers": sorted(CUSTOMERS.keys()),
        "count": len(CUSTOMERS),
    }
