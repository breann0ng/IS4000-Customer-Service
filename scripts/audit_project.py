import os
import sqlite3
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from google import genai
import requests

def print_status(component, status, detail=""):
    color = "\033[92m" if status == "PASS" else "\033[91m"
    reset = "\033[0m"
    print(f"[{color}{status}{reset}] {component:.<30} {detail}")

async def check_api_keys():
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

    if not api_key or "your" in api_key.lower():
        print_status("Gemini API Key", "FAIL", "Key is missing or placeholder")
    else:
        try:
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=model_name,
                contents="ping"
            )
            if response:
                print_status("Gemini Connectivity", "PASS", f"Model: {model_name}")
        except Exception as e:
            error_msg = str(e)
            if "404" in error_msg:
                error_msg = f"Model '{model_name}' not found. Check GEMINI_MODEL in .env"
            print_status("Gemini Connectivity", "FAIL", error_msg)

    tavily_key = os.getenv("TAVILY_API_KEY")
    if not tavily_key or "tvly" not in tavily_key:
        print_status("Tavily API Key", "FAIL", "Key is missing or invalid")
    else:
        try:
            resp = requests.post("https://api.tavily.com/search", json={"api_key": tavily_key, "query": "UBS", "max_results": 1})
            if resp.status_code == 200:
                print_status("Tavily Connectivity", "PASS")
            else:
                print_status("Tavily Connectivity", "FAIL", f"Status {resp.status_code}")
        except Exception as e:
            print_status("Tavily Connectivity", "FAIL", str(e))

    ls_key = os.getenv("LANGSMITH_API_KEY")
    if not ls_key or "lsv2" not in ls_key:
        print_status("LangSmith Key", "FAIL", "Missing or invalid. Tracing will be disabled.")
    else:
        print_status("LangSmith Config", "PASS", f"Project: {os.getenv('LANGSMITH_PROJECT', 'ubs-chatbot')}")

def check_database():
    db_path = Path("data/persona.db")
    if not db_path.exists():
        print_status("SQLite Database", "FAIL", "persona.db not found")
        return
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        tables = ["profiles", "accounts", "portfolios", "credit"]
        missing = [t for t in tables if not cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{t}'").fetchone()]
        if missing:
            print_status("Database Schema", "FAIL", f"Missing tables: {', '.join(missing)}")
        else:
            count = cursor.execute("SELECT COUNT(*) FROM profiles").fetchone()[0]
            print_status("Database Data", "PASS", f"{count} personas loaded")
        conn.close()
    except Exception as e:
        print_status("Database Check", "FAIL", str(e))

def check_fallbacks():
    graph_path = Path("apps/api/workflow/graph.py")
    if graph_path.exists():
        content = graph_path.read_text(encoding="utf-8")
        if "_synthesizer_fallback" in content and "resiliency_manager" in content:
            print_status("Fallback Implementation", "PASS", "Fail-fast logic detected")
        else:
            print_status("Fallback Implementation", "FAIL", "Fallback logic missing")
    else:
        print_status("Fallback Implementation", "FAIL", "graph.py missing")

if __name__ == "__main__":
    print("\n--- Project Configuration Audit ---\n")
    asyncio.run(check_api_keys())
    check_database()
    check_fallbacks()
    print("\n-----------------------------------\n")
