"""
mocks/base.py

Shared logic for mock MCP servers. 
Provides a common way to load customer data and handle JSON-RPC like requests.
"""

import json
import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("mock_base")
logging.basicConfig(level=logging.INFO)

CUSTOMER_DATA_DIR = Path(__file__).parent / "customer_data"

class MockDatabase:
    def __init__(self):
        self.customers: dict[str, dict] = {}
        self._load_customers()

    def _load_customers(self):
        if not CUSTOMER_DATA_DIR.exists():
            logger.error(f"Customer data directory not found: {CUSTOMER_DATA_DIR}")
            return

        for fpath in CUSTOMER_DATA_DIR.glob("C-*.json"):
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                cid = data["profile"]["customer_id"]
                self.customers[cid] = data
            except Exception as e:
                logger.error(f"Failed to load {fpath.name}: {e}")
        
        logger.info(f"Loaded {len(self.customers)} customers.")

    def get_customer(self, customer_id: str) -> Optional[dict]:
        return self.customers.get(customer_id)

    def search_customers(self, query: str) -> list[dict]:
        query = query.lower()
        results = []
        for cid, data in self.customers.items():
            if query in data["profile"]["full_name"].lower():
                results.append({
                    "customer_id": cid,
                    "full_name": data["profile"]["full_name"],
                    "segment": data["profile"]["segment"]
                })
        return results

# Singleton instance
db = MockDatabase()
