# UBS Customer Service Chatbot

AI-powered customer service chatbot for UBS Wealth Management, serving High Net Worth Individual (HNWI) clients. Built with a LangGraph plan-and-execute agentic workflow, Gemini 3.1 Pro, FastAPI backend, and React frontend.

## Table of Contents

- [Architecture](#architecture)
- [Specialist Agents](#specialist-agents)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Getting Started](#getting-started)
- [Docker (Full Stack)](#docker-full-stack)
- [RAG Document Ingestion](#rag-document-ingestion)
- [Development Tasks](#development-tasks)
- [API Endpoints](#api-endpoints)
- [API Client Generation](#api-client-generation)
- [Environment Variables](#environment-variables)
- [Tech Stack](#tech-stack)
- [Streaming & Thinking Steps](#streaming--thinking-steps)
- [Sample Queries](#sample-queries)
- [Future Work](#future-work)

## Architecture

```
Client (React) ──> FastAPI ──> LangGraph Workflow
                     │              │
                     │         ┌────┴─────┐
                     │      Planner    Synthesizer
                     │         │
                     │    ┌────┴────────────────────────────┐
                     │    │         Executor (loop)         │
                     │    │                                 │
                     │    │  ┌─────────────┐ ┌───────────┐  │
                     │    │  │  Wealth     │ │  Private  │  │
                     │    │  │  Advisory   │ │  Banking  │  │
                     │    │  └──────┬──────┘ └─────┬─────┘  │
                     │    │  ┌──────┴──────┐ ┌─────┴─────┐  │
                     │    │  │  Client     │ │  Lending  │  │
                     │    │  │  Services   │ │  & Credit │  │
                     │    │  └──────┬──────┘ └─────┬─────┘  │
                     │    │  ┌──────┴──────┐ ┌─────┴─────┐  │
                     │    │  │ Compliance  │ │    FX &   │  │
                     │    │  │   & Tax     │ │  Treasury │  │
                     │    │  └─────────────┘ └───────────┘  │
                     │    └──────────────┬──────────────────┘
                     │                   │
                     │         MCP Servers (Streamable HTTP)
                     │         ├── Banking Ops    :9001
                     │         ├── Knowledge      :9002
                     │         ├── Service Wkflow :9003
                     │         └── RAG MCP        :9004
                     │
              ┌──────┼──────────────────┐
           Postgres  Redis           LangSmith
        (sessions,   (mem0)           (tracing)
        pgvector RAG)
```

**Escalation Check** inspects queries for high-distress or advisory intents (e.g., "What should I invest in?"), immediately bypassing the LLM workflow to return a static Relationship Manager response. All inputs are sanitized by the **Security Middleware**, which masks PII (NRIC, account numbers) and detects prompt injection attempts before they reach the LLM.

**Planner** analyzes the remaining client queries using Gemini 3.1 structured output and routes to one or more specialist agents. Simple greetings are handled via high-efficiency direct responses. **Executor** dispatches steps sequentially to the selected agents, each connected to MCP servers via Streamable HTTP. **Synthesizer** combines all agent outputs into a single polished response with follow-up suggestions and escalation flags.

All LLM calls use **Gemini structured outputs** (Pydantic models) for reliable parsing.

## Specialist Agents

| Agent                | MCP Server               | Responsibilities                                                                               |
| -------------------- | ------------------------ | ---------------------------------------------------------------------------------------------- |
| **Wealth Advisory**  | Banking Ops (:9001)      | Portfolio performance, investment strategy, market insights (Tavily live search), asset allocation, estate planning |
| **Private Banking**  | Knowledge (:9002)        | Account operations, fund transfers, card services, statements, multi-currency management       |
| **Client Services**  | Service Workflow (:9003) | Onboarding, KYC/AML, document requests, appointments, escalations (uses RAG)                   |
| **Lending & Credit** | Banking Ops (:9001)      | Lombard lending, mortgages, credit lines, structured lending, margin facilities                |
| **Compliance & Tax** | Knowledge (:9002)        | CRS/FATCA reporting, cross-border tax, regulatory updates, documentation (uses RAG)            |
| **FX & Treasury**    | Service Workflow (:9003) | Foreign exchange, currency hedging, FX derivatives, treasury management                        |

## Project Structure

```
├── apps/
│   ├── api/                    FastAPI backend
│   │   ├── auth/               LDAP authentication (mock) + JWT
│   │   ├── chat/               Chat session CRUD + message handling
│   │   ├── database/           SQLAlchemy async models (Postgres + pgvector)
│   │   ├── memory/             mem0 + Redis short-context memory (HuggingFace embeddings)
│   │   ├── workflow/           LangGraph agentic workflow
│   │   │   ├── agents/         6 specialist agents
│   │   │   ├── tools/          MCP client + RAG retrieval tool
│   │   │   ├── planner.py      Structured plan generation (Greetings handled here)
│   │   │   ├── executor.py     Agent dispatch loop
│   │   │   ├── graph.py        StateGraph definition + synthesizer
│   │   │   └── state.py        Pydantic state/output models
│   │   ├── security/           Input guards (PII masking, prompt injection)
│   │   ├── config.py           Pydantic Settings (.env)
│   │   └── main.py             App entrypoint + Scalar API docs
│   └── ui/                     React + TypeScript frontend (Vite)
│       ├── src/
│       │   ├── api/generated/  Auto-generated TypeScript client
│       │   ├── components/     Sidebar, ChatWindow, MessageBubble, ThinkingIndicator,
│       │   │                   StructuredMessage (dashboard renderer), ChartCard (SVG charts)
│       │   └── pages/          LoginPage, ChatPage
├── rag/                        RAG pipeline + server
│   ├── ingest.py               PDF/DOCX → PostgreSQL pgvector (cosine similarity)
│   └── server.py               MCP server that queries pgvector for top-k chunks
├── mcp_servers/                Mock MCP servers for development
├── docs/                       Source documents for RAG (PDF/DOCX)
├── scripts/
│   ├── export_openapi.py       Export OpenAPI JSON from FastAPI app
│   └── check_openapi_drift.py  CI check: committed schema matches live app
├── pyproject.toml              Dependencies + poe tasks
├── docker-compose.yml          All services (Postgres, Redis, mocks, RAG, backend, frontend)
└── .env.example                Environment variable template
```

## Prerequisites

- **Python 3.12+**
- **uv** (Python package manager)
- **Node.js 22+** and **pnpm**
- **Docker** and **Docker Compose**

## Getting Started

### 1. Install dependencies

```bash
uv sync
cd apps/ui && pnpm install
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set your `GEMINI_API_KEY`. The project uses `gemini-3.1-pro-preview` by default.

### 3. Ingest RAG Documents

Ensure Postgres is running (`docker compose up -d postgres`), then:

```bash
poe rag-ingestion
```

### 4. Run Everything (Docker)

```bash
poe docker-up
```

- Frontend: http://localhost:3000 (Docker) / http://localhost:5173 (dev)
- Backend API: http://localhost:8000
- Scalar API Docs: http://localhost:8000/docs

## Development Tasks

| Task                      | Description                                                       |
| ------------------------- | ----------------------------------------------------------------- |
| `poe dev-api`             | Start the FastAPI backend with hot reload                         |
| `poe dev-ui`              | Start the React frontend dev server                               |
| `poe generate-api-client` | Export OpenAPI schema and regenerate TypeScript client            |
| `poe check`               | Format, lint, type-check Python code, and check for OpenAPI drift |
| `poe mock-mcp`            | Start all 3 mock MCP servers (:9001, :9002, :9003)                |
| `poe rag-server`          | Start the RAG MCP server querying pgvector on port 9004           |
| `poe rag-ingestion`       | Ingest documents from docs/ into pgvector                         |

## Environment Variables

| Variable                  | Default                         | Description                                           |
| ------------------------- | ------------------------------- | ----------------------------------------------------- |
| `GEMINI_API_KEY`          | —                               | Google Gemini API key                                 |
| `GEMINI_MODEL`            | `gemini-3.1-flash-lite-preview` | Gemini model identifier                               |
| `DATABASE_URL`            | `postgresql+asyncpg://...`      | Postgres connection string                            |
| `REDIS_URL`               | `redis://localhost:6379/0`      | Redis connection string                               |
| `EMBEDDING_MODEL_NAME`    | `sentence-transformers/all-MiniLM-L6-v2` | HuggingFace embedding model (auto-downloaded) |
| `RAG_TOP_K`               | `5`                             | Number of RAG chunks returned per query               |
| `JWT_SECRET_KEY`          | —                               | Secret for signing JWT tokens (change in production)  |
| `JWT_ALGORITHM`           | `HS256`                         | JWT signing algorithm                                 |
| `JWT_EXPIRATION_MINUTES`  | `60`                            | Token validity duration (minutes)                     |
| `LANGSMITH_API_KEY`       | —                               | Optional: LangSmith API key for LLM tracing           |
| `LANGSMITH_PROJECT`       | `ubs-chatbot`                   | LangSmith project name                                |
| `MCP_BANKING_OPS_URL`     | `http://localhost:9001/mcp`     | Wealth advisory & banking ops MCP server              |
| `MCP_KNOWLEDGE_URL`       | `http://localhost:9002/mcp`     | Private banking & compliance MCP server               |
| `MCP_SERVICE_WORKFLOW_URL`| `http://localhost:9003/mcp`     | Client services & FX treasury MCP server              |
| `MCP_RAG_SERVER_URL`      | `http://localhost:9004/mcp`     | RAG retrieval MCP server                              |
| `TAVILY_API_KEY`          | —                               | Tavily API key for live market data (Wealth Advisory) |
| `LOG_LEVEL`               | `INFO`                          | Log verbosity (DEBUG, INFO, WARNING, ERROR)           |

## Tech Stack

| Layer         | Technology                             |
| ------------- | -------------------------------------- |
| LLM           | Google Gemini 3.1 (structured outputs) |
| Orchestration | LangGraph (plan-and-execute)           |
| Backend       | FastAPI, SQLAlchemy (async)            |
| Frontend      | React 19, TypeScript, Vite, Radix UI   |
| Database      | PostgreSQL 16 + **pgvector**           |
| Memory        | mem0 + Redis                           |
| Embeddings    | sentence-transformers (local)          |
| Integration   | MCP (Streamable HTTP)                  |
| Live Search   | Tavily (market data for Wealth Advisory)|

## Streaming & Thinking Steps

The UI streams responses via SSE, showing intermediate thinking steps:

1. **`planning`** — Planner's reasoning and step list.
2. **`agent_step`** — Specialist agent results as they complete.
3. **`synthesizing`** — Synthesizer composing the final response.
4. **`done`** — Final persisted message.

## Dashboard UI

Wealth Advisory responses are rendered as an interactive dashboard:

- **Metric Cards** — Key figures (AUM, YTD return, allocation) with trend indicators (▲/▼).
- **SVG Charts** — Pie, bar, and line charts parsed from JSON embedded in the LLM response. Rendered natively with no external chart library.
- **Colored Section Cards** — `###` headings map to themed cards (green, blue, teal, indigo, amber, violet) cycling automatically.
- **Suggested Questions** — Clickable follow-up buttons injected by the Synthesizer.
- **GFM Tables** — Portfolio overview tables rendered with styled headers and rows.

The `StructuredMessage` component handles all parsing (heading normalisation, JSON chart extraction) and the `ChartCard` component renders pie/bar/line SVG charts via the `ChartData` interface.

## Sample Queries

- **Greeting**: "Hello" (Direct response path)
- **Portfolio**: "How is my portfolio performing?" (Wealth Advisory → dashboard with charts)
- **Market Outlook**: "What is the current macroeconomic outlook?" (Wealth Advisory → Tavily live search)
- **Multi-step**: "What's my balance and what are the current FX rates?" (Private Banking + FX Treasury)
- **RAG**: "What are the onboarding requirements for HNW clients?" (Client Services + RAG)
- **Lending**: "What Lombard lending options are available?" (Lending & Credit)

## Future Work

- Streaming chart rendering as agent steps arrive
- Multi-currency portfolio view with live FX overlay
- PDF export of dashboard responses
- Persistent notification centre for RM escalations
