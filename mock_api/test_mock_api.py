"""
test_mock_api.py

Quick smoke test for all mock API endpoints.
Run while the server is up:  python test_mock_api.py

Requires: pip install requests
"""

from __future__ import annotations
import requests

BASE = "http://localhost:8080"
CUSTOMERS = ["C-001", "C-002", "C-003", "C-004", "C-005"]

PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"


def headers(customer_id: str) -> dict:
    return {"Authorization": f"Bearer {customer_id}"}


def test(label: str, resp: requests.Response, expect_status: int = 200) -> bool:
    ok = resp.status_code == expect_status
    icon = PASS if ok else FAIL
    print(f"  {icon} [{resp.status_code}] {label}")
    if not ok:
        print(f"       → {resp.text[:200]}")
    return ok


def run_tests():
    print(f"\n{'='*55}")
    print("UBS Mock API Smoke Tests")
    print(f"{'='*55}\n")

    passed = failed = 0

    # Health check
    print("── Health ──")
    r = requests.get(f"{BASE}/api/mock/health")
    if test("GET /health", r): passed += 1
    else: failed += 1

    # Per-customer tests
    for cid in CUSTOMERS:
        h = headers(cid)
        print(f"\n── Customer {cid} ──")

        tests = [
            ("GET /customers/me",           requests.get(f"{BASE}/api/mock/customers/me", headers=h)),
            ("GET /accounts",               requests.get(f"{BASE}/api/mock/accounts", headers=h)),
            ("GET /transactions",           requests.get(f"{BASE}/api/mock/transactions", headers=h)),
            ("GET /portfolio",              requests.get(f"{BASE}/api/mock/portfolio", headers=h)),
            ("GET /portfolio/holdings",     requests.get(f"{BASE}/api/mock/portfolio/holdings", headers=h)),
            ("GET /credit",                 requests.get(f"{BASE}/api/mock/credit", headers=h)),
            ("GET /real-estate",            requests.get(f"{BASE}/api/mock/real-estate", headers=h)),
            ("GET /appointments",           requests.get(f"{BASE}/api/mock/appointments", headers=h)),
            ("GET /notifications",          requests.get(f"{BASE}/api/mock/notifications", headers=h)),
            ("GET /fx-rates",               requests.get(f"{BASE}/api/mock/fx-rates", headers=h)),
            ("GET /net-worth-summary",      requests.get(f"{BASE}/api/mock/net-worth-summary", headers=h)),
        ]
        for label, resp in tests:
            if test(label, resp): passed += 1
            else: failed += 1

    # Appointment booking test (C-001)
    print("\n── Appointment Booking (C-001) ──")
    h = headers("C-001")
    r = requests.post(f"{BASE}/api/mock/appointments", headers=h, json={
        "appointment_type": "Portfolio Review",
        "preferred_date": "2026-04-01",
        "preferred_time": "10:00",
        "location_preference": "In-person",
        "notes": "Want to discuss NVDA position sizing",
    })
    if test("POST /appointments (weekday)", r): passed += 1
    else: failed += 1

    # Weekend rejection test
    r = requests.post(f"{BASE}/api/mock/appointments", headers=h, json={
        "appointment_type": "Portfolio Review",
        "preferred_date": "2026-03-22",   # Sunday
        "preferred_time": "10:00",
        "location_preference": "Video call",
    })
    if test("POST /appointments (weekend — expect 422)", r, expect_status=422): passed += 1
    else: failed += 1

    # ── Rates API (no auth needed) ──
    print("\n── Rates API ──")
    rates_tests = [
        ("GET /api/rates/mortgage",  requests.get(f"{BASE}/api/rates/mortgage")),
        ("GET /api/rates/lombard",   requests.get(f"{BASE}/api/rates/lombard")),
        ("GET /api/rates/savings",   requests.get(f"{BASE}/api/rates/savings")),
        ("GET /api/rates/cards",     requests.get(f"{BASE}/api/rates/cards")),
        ("GET /api/rates/fx",        requests.get(f"{BASE}/api/rates/fx")),
        ("GET /api/rates/all",       requests.get(f"{BASE}/api/rates/all")),
    ]
    for label, resp in rates_tests:
        if test(label, resp): passed += 1
        else: failed += 1

    # ── Applications API ──
    print("\n── Applications API (C-001) ──")
    h = headers("C-001")
    apps_tests = [
        ("GET /api/applications/types",  requests.get(f"{BASE}/api/applications/types", headers=h)),
        ("GET /api/applications",         requests.get(f"{BASE}/api/applications", headers=h)),
        ("GET /api/applications/APP-001-A", requests.get(f"{BASE}/api/applications/APP-001-A", headers=h)),
    ]
    for label, resp in apps_tests:
        if test(label, resp): passed += 1
        else: failed += 1

    # Submit a new application
    r = requests.post(f"{BASE}/api/applications", headers=h, json={
        "application_type": "card_replacement",
        "description": "UBS Visa Infinite damaged — requesting replacement",
        "priority": "Normal",
    })
    if test("POST /api/applications (card replacement)", r): passed += 1
    else: failed += 1

    # Block account closure
    r = requests.post(f"{BASE}/api/applications", headers=h, json={
        "application_type": "account_closure",
        "description": "Close investment settlement account",
    })
    if test("POST /api/applications (account_closure — expect 422)", r, expect_status=422): passed += 1
    else: failed += 1

    # ── Auth failure test ──
    print("\n── Auth ──")
    r = requests.get(f"{BASE}/api/mock/accounts", headers={"Authorization": "Bearer INVALID"})
    if test("Invalid customer ID (expect 401)", r, expect_status=401): passed += 1
    else: failed += 1

    # Summary
    total = passed + failed
    print(f"\n{'='*55}")
    print(f"Results: {passed}/{total} passed  |  {failed} failed")
    print(f"{'='*55}\n")

    if failed == 0:
        print("All tests passed. Mock API is ready.\n")
    else:
        print(f"{failed} test(s) failed. Check output above.\n")


if __name__ == "__main__":
    try:
        requests.get(f"{BASE}/api/mock/health", timeout=3)
    except Exception:
        print(f"\n✗ Cannot reach {BASE}. Is the server running?")
        print("  Start it with:  uvicorn main:app --reload --port 8080\n")
        exit(1)

    run_tests()
