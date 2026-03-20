# Gemini Project Context: UBS Customer Service Chatbot

This project is an AI-powered customer service chatbot for UBS Wealth Management, specifically tailored for High-Net-Worth (HNW) clients. It uses an agentic "Plan-and-Execute" workflow powered by LangGraph and Google Gemini 3.1.

## Project Overview

- **Core Architecture:** Plan-and-Execute agentic workflow using LangGraph.
- **LLM Strategy:** Google Gemini 3.1 Pro/Flash with strict **structured outputs** via Pydantic models.
- **Backend:** FastAPI (Python 3.12), SQLAlchemy (Async), PostgreSQL (pgvector for RAG), Redis (mem0 for short-term memory).
- **Frontend:** React 19 (TypeScript, Vite), Radix UI, SSE (Server-Sent Events) for real-time "thinking" UI.
- **Data Integration:** Model Context Protocol (MCP) for secure, zero-trust access to core banking operations and knowledge bases.
- **Compliance:** Built with MAS FEAT principles in mind, including PII masking, input guarding, and explicit escalation to human Relationship Managers (RM).

## Directory Structure

- `apps/api/`: FastAPI backend implementation.
  - `auth/`: Mock LDAP + JWT authentication.
  - `chat/`: Session management and streaming message handling.
  - `workflow/`: LangGraph brain (planner, executor, synthesizer).
  - `security/`: PII masking and prompt injection guards.
- `apps/ui/`: React frontend.
  - `src/api/generated/`: Auto-generated TypeScript client from OpenAPI schema.
- `mcp_servers/`: Mock/Internal MCP servers (Banking Ops, Knowledge, Service Workflow).
- `rag/`: RAG pipeline and vector ingestion logic (PostgreSQL pgvector).
- `docs/`: Source documents for the RAG knowledge base.
- `scripts/`: Tooling for OpenAPI export and drift checking.

## Building and Running

The project uses `poethepoet` (poe) as a task runner.

### Prerequisites
- **Python 3.12+** (managed via `uv`)
- **Node.js 22+** (managed via `pnpm`)
- **Docker & Docker Compose**

### Setup
1. **Python Environment:** `uv sync`
2. **Frontend Dependencies:** `cd apps/ui && pnpm install`
3. **Environment:** `cp .env.example .env` (Add `GEMINI_API_KEY` for live mode)
4. **Infrastructure:** `docker compose up -d postgres redis`

### Execution
- **Full Stack (Docker):** `poe docker-up`
- **Development Mode (Individual Services):**
  - **Backend:** `poe dev-api` (Port 8000)
  - **Frontend:** `poe dev-ui` (Port 5173)
  - **MCP Servers:** `poe mock-mcp` (Ports 9001-9003)
  - **RAG Server:** `poe rag-server` (Port 9004)
- **RAG Ingestion:** `poe rag-ingestion` (Ingest docs from `docs/` into pgvector)

## Development Conventions

### Coding Style & Standards
- **Python:** Strictly follows PEP 8, uses `ruff` for formatting and linting.
- **Type Safety:** Python uses Pydantic for models and `pyright` (via `poe check`) for static analysis. TypeScript frontend is fully typed.
- **API First:** The frontend client is auto-generated. Run `poe generate-api-client` after modifying backend models or routes.
- **Documentation:** API reference is served via Scalar at `/docs`.

### Agentic Workflow (LangGraph)
- **Planner:** Analyzes query and routes to one or more specialist agents. Greetings are handled via high-efficiency direct responses.
- **Executor:** Sequential dispatch of tasks to agents via MCP.
- **Synthesizer:** Polishes multiple agent outputs into a unified, premium response.
- **Escalation:** Explicit bypass for advisory/high-risk queries to human RMs.

### Security & Compliance
- **Zero-Trust:** Agents only access data through MCP; direct DB access for LLMs is prohibited.
- **PII Masking:** Middleware automatically masks sensitive data (NRIC, Account Numbers).
- **Auditability:** Every step (Planning, Execution, Synthesis) is logged and traceable.

## Key Commands Reference

| Task | Command |
| :--- | :--- |
| Start all services | `poe docker-up` |
| Run linting & checks | `poe check` |
| Sync API client | `poe generate-api-client` |
| Ingest RAG docs | `poe rag-ingestion` |
| Start mock MCPs | `poe mock-mcp` |
