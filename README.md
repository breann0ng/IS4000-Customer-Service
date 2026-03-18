# UBS Customer Service AI — Mock API & Knowledge Base

This project provides the backend infrastructure for a UBS Private Banking AI chatbot. It includes a **Mock Banking API** (for personal customer data) and a **Knowledge Base** (scraped from UBS public support and product pages).

## 🚀 Getting Started

### 1. Project Setup
```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Mac/Linux

# Install dependencies
pip install -r mock_api/requirements.txt
pip install -r web-scraping/requirements.txt
```

### 2. Running the Mock API
```bash
cd mock_api
uvicorn main:app --reload --port 8080
```
*   **Docs**: http://localhost:8080/docs (Swagger UI)
*   **Root**: http://localhost:8080/ (Lists all 10 demo customers)

---

## 🏦 Mock Banking API

### Authentication
All protected endpoints require an `Authorization` header. For the mock system, the **Customer ID** is your login token:
`Authorization: Bearer C-001` (to log in as Marcus Tan)

### Available Customers (C-001 to C-010)
| ID | Name | Segment | Focus |
|----|------|---------|-------|
| C-001 | Marcus Tan | UHNW | Tech entrepreneur |
| C-002 | Eleanor Voss | HNW | Retiree (CH) |
| C-003 | James Okafor | HNW | Business owner |
| ... | ... | ... | (See root endpoint for full list) |

### Key Endpoints
*   `GET /api/mock/customers/me` — Current profile & RM contact
*   `GET /api/mock/accounts` — Balances & accounts
*   `GET /api/mock/portfolio` — Investment performance & allocation
*   `POST /api/mock/appointments` — Book a meeting with an RM

---

## 🧠 Knowledge Base (RAG)

The knowledge base consists of **1,326 processed chunks** from the UBS public website and PDF brochures.

*   **Final Data File**: `web-scraping/output/chunks/all_chunks.jsonl`
*   **Contents**:
    *   **help_faq**: Support articles (Activation, PIN recovery, e-banking).
    *   **product_info**: Private banking services (Hypothek, Pension).
    *   **pdf_brochure**: Data from 44 official UBS PDF brochures.

### For LangGraph Integration:
Your RAG tool should load `all_chunks.jsonl` into a Vector Database (like ChromaDB or FAISS). 

The LLM is then responsible for orchestrating:
1.  **General Inquiries**: Use a "Search Knowledge" tool to query the `.jsonl` data.
2.  **Personal Requests**: Use an "API Call" tool to hit the Mock API endpoints using the current user's `customer_id`.

---

## 🛠 Project Structure
*   `mock_api/`: FastAPI server and customer JSON "database".
*   `web-scraping/`: Scripts and output for the RAG knowledge base.
*   `web-scraping/output/chunks/all_chunks.jsonl`: **The key file needed for the chatbot's RAG memory.**
