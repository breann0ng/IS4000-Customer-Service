import sqlite3
import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("mock_base")
logging.basicConfig(level=logging.INFO)

# Path to the centralized database
DB_PATH = Path(__file__).parent.parent / "data" / "persona.db"

class MockDatabase:
    def __init__(self):
        # We don't preload into memory anymore, we query as needed
        if not DB_PATH.exists():
            logger.error(f"Centralized database not found at: {DB_PATH}")
        else:
            logger.info(f"MockDatabase connected to centralized SQLite: {DB_PATH}")

    def _get_conn(self):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    def get_customer(self, customer_id: str) -> Optional[dict]:
        """Fetch full customer data (merged) from the DB."""
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            
            # 1. Profile
            cursor.execute("SELECT * FROM profiles WHERE customer_id = ? OR username = ?", (customer_id, customer_id))
            profile_row = cursor.fetchone()
            if not profile_row:
                conn.close()
                return None
            
            profile = dict(profile_row)
            cid = profile["customer_id"]
            data = {"profile": profile}
            
            # 2. Accounts
            cursor.execute("SELECT * FROM accounts WHERE customer_id = ?", (cid,))
            data["accounts"] = [dict(row) for row in cursor.fetchall()]
            
            # 3. Portfolio
            cursor.execute("SELECT * FROM portfolios WHERE customer_id = ?", (cid,))
            port = cursor.fetchone()
            data["portfolio"] = dict(port) if port else {}
            
            # 4. Credit
            cursor.execute("SELECT * FROM credit WHERE customer_id = ?", (cid,))
            credit = cursor.fetchone()
            data["credit"] = dict(credit) if credit else {}

            # 5. Nested / List items
            cursor.execute("SELECT * FROM credit_cards WHERE customer_id = ?", (cid,))
            data["credit"]["credit_cards"] = [dict(row) for row in cursor.fetchall()]

            cursor.execute("SELECT * FROM real_estate WHERE customer_id = ?", (cid,))
            data["real_estate"] = [dict(row) for row in cursor.fetchall()]

            cursor.execute("SELECT * FROM transactions WHERE customer_id = ?", (cid,))
            data["recent_transactions"] = [dict(row) for row in cursor.fetchall()]

            cursor.execute("SELECT * FROM appointments WHERE customer_id = ?", (cid,))
            data["appointments"] = [dict(row) for row in cursor.fetchall()]

            cursor.execute("SELECT * FROM notifications WHERE customer_id = ?", (cid,))
            data["notifications"] = [dict(row) for row in cursor.fetchall()]

            cursor.execute("SELECT * FROM applications WHERE customer_id = ?", (cid,))
            data["applications"] = [dict(row) for row in cursor.fetchall()]

            conn.close()
            return data
        except Exception as e:
            logger.error(f"Failed to get_customer {customer_id}: {e}")
            return None

    def search_customers(self, query: str) -> list[dict]:
        """Search profiles by name or ID."""
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            q = f"%{query}%"
            cursor.execute("""
                SELECT customer_id, full_name, segment 
                FROM profiles 
                WHERE full_name LIKE ? OR customer_id LIKE ? OR username LIKE ?
            """, (q, q, q))
            results = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return results
        except Exception as e:
            logger.error(f"Failed to search_customers with query '{query}': {e}")
            return []

# Singleton instance
db = MockDatabase()
