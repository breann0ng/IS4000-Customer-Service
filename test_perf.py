import time
import requests
import json
import argparse
from datetime import datetime

# Configuration
BASE_URL = "http://127.0.0.1:8000/api"
PERSONAS = {
    "mtan": "password123",
    "jsmith": "password123",
    "ajohnson": "password123"
}

TEST_QUESTIONS = [
    "What is my current total account balance?",
    "How is my portfolio performing YTD?",
    "What is my Lombard limit and current SGD/USD rate?"
]

def login(username, password):
    print(f"\n[Auth] Logging in as {username}...")
    url = f"{BASE_URL}/auth/login"
    try:
        response = requests.post(url, json={"username": username, "password": password})
        response.raise_for_status()
        token = response.json().get("access_token")
        print(f"[Auth] Success! Token acquired.")
        return token
    except Exception as e:
        print(f"[Auth] Failed: {e}")
        return None

def create_session(token, title):
    url = f"{BASE_URL}/chat/sessions"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.post(url, json={"title": title}, headers=headers)
        response.raise_for_status()
        return response.json().get("session_id")
    except Exception as e:
        print(f"[Session] Failed to create: {e}")
        return None

def ask_question(token, session_id, question):
    url = f"{BASE_URL}/chat/sessions/{session_id}/messages"
    headers = {"Authorization": f"Bearer {token}"}
    
    start_time = time.time()
    try:
        print(f"\n[Chat] Question: {question}")
        response = requests.post(url, json={"content": question}, headers=headers)
        duration = time.time() - start_time
        response.raise_for_status()
        
        data = response.json()
        message_data = data.get("message", {})
        content = message_data.get("content", "No content")
        
        # Check for fallback markers in the response content
        is_fallback = "Service Alert" in content or "raw data" in content.lower()
        path = "FALLBACK (Circuit Breaker active)" if is_fallback else "HEALTHY (LLM Summary)"
        
        print(f"[Chat] Response received in {duration:.2f} seconds via {path}")
        print("-" * 50)
        print(content[:500] + "..." if len(content) > 500 else content)
        print("-" * 50)
        
        return duration, is_fallback
    except Exception as e:
        print(f"[Chat] Failed: {e}")
        return None, None

def run_persona_test(username):
    token = login(username, PERSONAS[username])
    if not token: return
    
    session_id = create_session(token, f"Perf Test - {username} - {datetime.now().strftime('%H:%M:%S')}")
    if not session_id: return
    
    results = []
    for q in TEST_QUESTIONS:
        duration, was_fallback = ask_question(token, session_id, q)
        if duration:
            results.append({"question": q, "duration": duration, "fallback": was_fallback})
        
        # Mandatory wait to avoid 429 in live mode if not in fallback
        if not was_fallback:
            print(f"[Wait] Buffering for 10s to preserve Gemini quota...")
            time.sleep(10)
            
    return results

def main():
    parser = argparse.ArgumentParser(description="UBS Chatbot Performance & Accuracy Tester")
    parser.add_argument("--persona", choices=["mtan", "jsmith", "ajohnson", "all"], default="all")
    args = parser.parse_args()

    print("=" * 70)
    print(f"UBS CHATBOT PERFORMANCE TESTER — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 70)

    target_personas = ["mtan", "jsmith", "ajohnson"] if args.persona == "all" else [args.persona]
    
    all_results = {}
    for p in target_personas:
        print(f"\n>>> STARTING TEST FOR PERSONA: {p.upper()}")
        all_results[p] = run_persona_test(p)

    print("\n" + "=" * 70)
    print("FINAL PERFORMANCE SUMMARY")
    print("=" * 70)
    for p, results in all_results.items():
        if not results: continue
        avg_time = sum(r["duration"] for r in results) / len(results)
        fallback_count = sum(1 for r in results if r["fallback"])
        print(f"Persona: {p:10} | Avg Response: {avg_time:5.2f}s | Fallbacks: {fallback_count}/{len(results)}")
    print("=" * 70)

if __name__ == "__main__":
    main()
