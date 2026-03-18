"""
mock_db.py

Loads all customer JSON files from the customer_data/ directory
into an in-memory dict at startup. Drop-in replacement for seed_data.py.

Usage in mock_api_router.py:
    from mock_db import get_customer, get_all_customer_ids, search_customers
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Resolve customer_data/ relative to this file's location
CUSTOMER_DATA_DIR = Path(__file__).parent / "customer_data"

CUSTOMERS: dict[str, dict] = {}


def _load_customers() -> None:
    """Load all C-*.json files from customer_data/ into CUSTOMERS dict."""
    if not CUSTOMER_DATA_DIR.exists():
        logger.error(f"customer_data/ directory not found at {CUSTOMER_DATA_DIR}")
        return

    files = sorted(CUSTOMER_DATA_DIR.glob("C-*.json"))
    if not files:
        logger.error(f"No customer JSON files found in {CUSTOMER_DATA_DIR}")
        return

    for fpath in files:
        try:
            with open(fpath, encoding="utf-8") as f:
                data = json.load(f)
            customer_id = data["profile"]["customer_id"]
            CUSTOMERS[customer_id] = data
            logger.info(f"Loaded {customer_id}: {data['profile']['full_name']}")
        except Exception as e:
            logger.error(f"Failed to load {fpath.name}: {e}")

    logger.info(f"Loaded {len(CUSTOMERS)} customers from {CUSTOMER_DATA_DIR}")


# Load on import
_load_customers()


def get_customer(customer_id: str) -> dict | None:
    return CUSTOMERS.get(customer_id)


def get_all_customer_ids() -> list[str]:
    return sorted(CUSTOMERS.keys())


def search_customers(name: str) -> list[dict]:
    name_lower = name.lower()
    return [
        {
            "customer_id": cid,
            "full_name": data["profile"]["full_name"],
            "segment": data["profile"]["segment"],
        }
        for cid, data in CUSTOMERS.items()
        if name_lower in data["profile"]["full_name"].lower()
    ]


def reload() -> None:
    """Hot-reload all customer files (useful during development)."""
    CUSTOMERS.clear()
    _load_customers()
