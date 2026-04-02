import sqlite3
import json
import os
import glob
from pathlib import Path

DB_PATH = "data/persona.db"
CUSTOMER_DATA_DIR = "mocks/customer_data"
PROFILES_DIR = "mcp_servers/data/profiles"

# Target filters
TARGET_NAMES = ["Marcus Tan Wei Jian", "Alice Johnson", "John Smith"]
TARGET_IDS = ["C-001", "C-011", "C-02"]

def init_db(cursor):
    """Initialize the schema for the persona database."""
    tables = [
        "profiles", "accounts", "portfolios", "performance_history", 
        "credit", "credit_cards", "real_estate", "transactions", 
        "appointments", "notifications", "applications"
    ]
    for table in tables:
        cursor.execute(f"DROP TABLE IF EXISTS {table}")

    cursor.execute("""
        CREATE TABLE profiles (
            customer_id TEXT PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            preferred_name TEXT,
            segment TEXT,
            tier TEXT,
            risk_profile TEXT,
            aum_usd REAL,
            net_worth_usd REAL,
            relationship_manager TEXT,
            rm_email TEXT,
            address TEXT,
            email TEXT,
            mobile TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id TEXT,
            account_id TEXT,
            account_type TEXT,
            currency TEXT,
            balance REAL,
            available_balance REAL,
            status TEXT,
            FOREIGN KEY(customer_id) REFERENCES profiles(customer_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE portfolios (
            customer_id TEXT PRIMARY KEY,
            total_value_usd REAL,
            ytd_return_pct REAL,
            one_year_return_pct REAL,
            equities_pct REAL,
            fixed_income_pct REAL,
            cash_pct REAL,
            mandate_type TEXT,
            FOREIGN KEY(customer_id) REFERENCES profiles(customer_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE performance_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id TEXT,
            month TEXT,
            value_usd REAL,
            return_pct REAL,
            FOREIGN KEY(customer_id) REFERENCES profiles(customer_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE credit (
            customer_id TEXT PRIMARY KEY,
            lombard_limit REAL,
            lombard_drawn REAL,
            lombard_available REAL,
            mortgage_outstanding REAL,
            mortgage_property TEXT,
            mortgage_interest_rate REAL,
            FOREIGN KEY(customer_id) REFERENCES profiles(customer_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE credit_cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id TEXT,
            product TEXT,
            limit_usd REAL,
            outstanding_usd REAL,
            status TEXT,
            FOREIGN KEY(customer_id) REFERENCES profiles(customer_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE real_estate (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id TEXT,
            property TEXT,
            location TEXT,
            value_local REAL,
            loan_local REAL,
            FOREIGN KEY(customer_id) REFERENCES profiles(customer_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id TEXT,
            date TEXT,
            description TEXT,
            amount REAL,
            currency TEXT,
            account_id TEXT,
            FOREIGN KEY(customer_id) REFERENCES profiles(customer_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE appointments (
            appointment_id TEXT PRIMARY KEY,
            customer_id TEXT,
            type TEXT,
            date TEXT,
            time TEXT,
            rm TEXT,
            location TEXT,
            status TEXT,
            FOREIGN KEY(customer_id) REFERENCES profiles(customer_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE notifications (
            id TEXT PRIMARY KEY,
            customer_id TEXT,
            type TEXT,
            message TEXT,
            date TEXT,
            read BOOLEAN,
            FOREIGN KEY(customer_id) REFERENCES profiles(customer_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE applications (
            application_id TEXT PRIMARY KEY,
            customer_id TEXT,
            application_type TEXT,
            description TEXT,
            status TEXT,
            submitted_date TEXT,
            expected_completion TEXT,
            notes TEXT,
            FOREIGN KEY(customer_id) REFERENCES profiles(customer_id)
        )
    """)

def ingest_from_files(cursor, json_files, source_name):
    print(f"Checking {len(json_files)} profiles from {source_name}...")
    username_map = {
        "C-001": "mtan",
        "C-011": "jsmith",
        "C-02": "ajohnson"
    }

    ingested_count = 0
    for file_path in json_files:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        profile = data.get("profile", {})
        customer_id = profile.get("customer_id")
        full_name = profile.get("full_name", "")
        
        # Filter: check ID or Name
        if customer_id not in TARGET_IDS and full_name not in TARGET_NAMES:
            continue

        # Check if already ingested (ID or Name uniqueness)
        cursor.execute("SELECT 1 FROM profiles WHERE customer_id = ? OR full_name = ?", (customer_id, full_name))
        if cursor.fetchone():
            continue

        username = username_map.get(customer_id) or profile.get("username") or full_name.split()[0].lower()

        # 1. Profile
        cursor.execute("""
            INSERT INTO profiles (
                customer_id, username, full_name, preferred_name, segment, tier, 
                risk_profile, aum_usd, net_worth_usd, relationship_manager, 
                rm_email, address, email, mobile
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            customer_id, username, profile.get("full_name"), 
            profile.get("preferred_name"), profile.get("segment"), profile.get("tier"),
            profile.get("risk_profile"), profile.get("aum_with_ubs_usd") or profile.get("aum_usd", 0),
            profile.get("net_worth_usd", 0), profile.get("relationship_manager"),
            profile.get("rm_email"), profile.get("address"), profile.get("email"), profile.get("mobile")
        ))

        # 2. Accounts
        for acc in data.get("accounts", []):
            balance = acc.get("balance") or acc.get("total_usd_equivalent", 0)
            cursor.execute("""
                INSERT INTO accounts (customer_id, account_id, account_type, currency, balance, available_balance, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (customer_id, acc.get("account_id"), acc.get("account_type"), acc.get("currency"), balance, acc.get("available_balance"), acc.get("status")))

        # 3. Portfolios
        port = data.get("portfolio", {})
        alloc = port.get("allocation", {})
        equities = alloc.get("Public Equities", {}).get("pct", 0) or alloc.get("equities", {}).get("pct", 0)
        fixed = alloc.get("Fixed Income", {}).get("pct", 0) or alloc.get("fixed_income", {}).get("pct", 0)
        cash = alloc.get("Cash", {}).get("pct", 0) or alloc.get("Cash within Portfolio", {}).get("pct", 0)
        
        cursor.execute("""
            INSERT INTO portfolios (
                customer_id, total_value_usd, ytd_return_pct, one_year_return_pct, 
                equities_pct, fixed_income_pct, cash_pct, mandate_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            customer_id,
            port.get("total_value_usd", 0),
            port.get("ytd_return_pct", 0),
            port.get("one_year_return_pct", 0),
            equities, fixed, cash,
            port.get("mandate_type")
        ))

        # 4. Performance History
        base_val = profile.get("aum_with_ubs_usd") or 10000000
        history = [
            ("Oct 2025", base_val * 0.92, -1.5),
            ("Nov 2025", base_val * 0.94, 2.1),
            ("Dec 2025", base_val * 0.93, -1.1),
            ("Jan 2026", base_val * 0.96, 3.2),
            ("Feb 2026", base_val * 0.97, 1.0),
            ("Mar 2026", base_val, port.get("ytd_return_pct", 0))
        ]
        for m, v, r in history:
            cursor.execute("""
                INSERT INTO performance_history (customer_id, month, value_usd, return_pct)
                VALUES (?, ?, ?, ?)
            """, (customer_id, m, v, r))

        # 5. Credit
        credit = data.get("credit", {})
        lombard = credit.get("lombard_facility", {})
        mortgage = credit.get("mortgage", {})
        cursor.execute("""
            INSERT INTO credit (
                customer_id, lombard_limit, lombard_drawn, lombard_available, 
                mortgage_outstanding, mortgage_property, mortgage_interest_rate
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            customer_id,
            lombard.get("limit_usd", 0),
            lombard.get("drawn_usd", 0),
            lombard.get("available_usd", 0),
            mortgage.get("outstanding_sgd", 0),
            mortgage.get("property"),
            mortgage.get("interest_rate_pct", 0)
        ))

        # 6. Credit Cards
        for card in credit.get("credit_cards", []):
            cursor.execute("""
                INSERT INTO credit_cards (customer_id, product, limit_usd, outstanding_usd, status)
                VALUES (?, ?, ?, ?, ?)
            """, (customer_id, card.get("product"), card.get("limit_usd"), card.get("outstanding_usd"), card.get("status")))

        # 7. Real Estate
        for re in data.get("real_estate", []):
            cursor.execute("""
                INSERT INTO real_estate (customer_id, property, location, value_local, loan_local)
                VALUES (?, ?, ?, ?, ?)
            """, (customer_id, re.get("property"), re.get("location"), re.get("value_sgd") or re.get("value_gbp") or re.get("value_aud", 0), re.get("loan_sgd") or re.get("loan_gbp") or re.get("loan_aud", 0)))

        # 8. Transactions
        for tx in data.get("recent_transactions", []):
            cursor.execute("""
                INSERT INTO transactions (customer_id, date, description, amount, currency, account_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (customer_id, tx.get("date"), tx.get("description"), tx.get("amount"), tx.get("currency"), tx.get("account")))

        # 9. Appointments
        for apt in data.get("appointments", []):
            cursor.execute("""
                INSERT INTO appointments (appointment_id, customer_id, type, date, time, rm, location, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (apt.get("appointment_id"), customer_id, apt.get("type"), apt.get("date"), apt.get("time"), apt.get("rm"), apt.get("location"), apt.get("status")))

        # 10. Notifications
        for note in data.get("notifications", []):
            cursor.execute("""
                INSERT INTO notifications (id, customer_id, type, message, date, read)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (note.get("id"), customer_id, note.get("type"), note.get("message"), note.get("date"), note.get("read")))

        # 11. Applications
        for app in data.get("applications", []):
            cursor.execute("""
                INSERT INTO applications (application_id, customer_id, application_type, description, status, submitted_date, expected_completion, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (app.get("application_id"), customer_id, app.get("application_type"), app.get("description"), app.get("status"), app.get("submitted_date"), app.get("expected_completion"), app.get("notes")))

        ingested_count += 1
    
    print(f"Ingested {ingested_count} target profiles from {source_name}.")

def ingest():
    if not os.path.exists("data"):
        os.makedirs("data")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    init_db(cursor)

    # Check both sources
    mock_files = glob.glob(os.path.join(CUSTOMER_DATA_DIR, "*.json"))
    ingest_from_files(cursor, mock_files, "mocks/customer_data")

    profile_files = glob.glob(os.path.join(PROFILES_DIR, "*.json"))
    ingest_from_files(cursor, profile_files, "mcp_servers/data/profiles")

    conn.commit()
    conn.close()
    print("Ingestion complete. Centralized DB contains only John Smith, Alice Johnson, and Marcus Tan.")

if __name__ == "__main__":
    ingest()
