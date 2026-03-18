# UBS Customer Service AI — Multi-Agent MCP Architecture

This project implements a professional, modular architecture for a UBS Private Banking AI chatbot, following a **Specialist Agent + MCP Server** design.

## 🚀 Architectural Overview

We have migrated the monolithic Mock API into three specialist **MCP (Model Context Protocol)** servers to enable fine-grained agentic routing.

### 🖥️ Specialist MCP Servers
| Server | Port | Responsibilities |
|---|---|---|
| **Banking Ops** | `9001` | Wealth Advisory, Portfolio performance, Lending & Credit. |
| **Knowledge** | `9002` | Private Banking operations & RAG (Retrieval-Augmented Generation). |
| **Service Workflow** | `9003` | Client Services, Appointments, FX Rates. |

## 📁 Project Structure

*   **/apps/**: Future home for the FastAPI backend and React frontend.
*   **/mocks/**: Specialist MCP servers and mock customer data.
    *   `customer_data/`: JSON files for 10 demo customers (C-001 to C-010).
*   **/rag/**: Knowledge base retrieval logic and data.
    *   `data/all_chunks.jsonl`: **1,326 processed chunks** from UBS site & PDFs.
*   **/docs/**: Source documents for the RAG pipeline.

## 🛠 Running the Servers

To start the specialist agents for local development:

```bash
# Terminal 1: Banking Ops (Port 9001)
python mocks/banking_ops_server.py

# Terminal 2: Knowledge & Private Banking (Port 9002)
python mocks/knowledge_server.py

# Terminal 3: Service Workflow (Port 9003)
python mocks/service_workflow_server.py
```

## 🧠 Integration Guide (for LangGraph)

1.  **Auth**: All endpoints require `Authorization: Bearer <customer_id>`.
2.  **RAG**: The `Knowledge` agent (Port 9002) is connected to the RAG module in `/rag/server.py`.
3.  **Agents**: Each specialist agent should be configured as a tool in LangGraph, pointed at its respective local port.