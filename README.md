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
                     │         MCP Servers (Shared SQLite Data)
                     │         ├── Banking Ops    :9001 ──┐
                     │         ├── Knowledge      :9002 ──┼──> [data/persona.db]
                     │         ├── Service Wkflow :9003 ──┘
                     │         └── RAG MCP        :9004 ──> [Postgres]
                     │
              ┌──────┼──────────────────┐
           Postgres  Redis           LangSmith
        (sessions,   (mem0: HF       (tracing)
        pgvector RAG)  embed + optional Ollama)

**Escalation Check** inspects queries for high-distress or advisory intents (e.g., "What should I invest in?"), immediately bypassing the LLM workflow to return a static Relationship Manager response. All inputs are sanitized by the **Security Middleware**, which masks PII (NRIC, account numbers) and detects prompt injection attempts before they reach the LLM.

**Planner** analyzes the remaining client queries using Gemini structured output and routes to one or more specialist agents. Simple greetings are handled via high-efficiency direct responses. **Executor** dispatches steps sequentially to the selected agents, propagating the **authenticated username (persona)** through the workflow to ensure data isolation. 

To ensure **full, complete responses** without truncation, the system uses a **Decomposed Synthesis** strategy:
1. **The Writer**: A standard LLM call generates the final **Markdown Report** seen by the user (Summary, Market Context, Next Steps). This removes JSON-mode length constraints that can cause responses to cut off.
2. **The Extractor**: A specialized structured call extracts metadata (metrics, confidence, follow-up suggestions) from the generated response and agent findings to populate the UI dashboard. 

All LLM calls are monitored by a central **Resiliency Manager** to handle API availability.

## Data Architecture & LLM Resiliency

The system is designed for high availability and consistent performance, even during upstream API outages or quota limits.

### 1. Data Layers (Mocked vs. Live)
- **Centralized SQLite** (`data/persona.db`): The primary source of truth for the local environment. It merges all persona data (profiles, accounts, portfolios, credit) into a queryable structure, replacing fragmented JSON mocks with a relational data layer accessible by all MCP servers.
- **Dynamic Search**: The data layer supports SQL-based searching by `full_name`, `customer_id`, or `username`, allowing specialists to find contextually relevant information dynamically.
- **Persistent Store (Postgres)**: Stores chat history, user sessions, and RAG vector embeddings (`pgvector`).
- **Live Search (Tavily)**: Fetches real-time market data for the Wealth Advisory agent.

### 2. Conversational memory (mem0) — no Gemini/OpenAI billing

Short-context memory uses **mem0** with **Redis** and **local Hugging Face embeddings** (`sentence-transformers`). Cloud LLM keys are **not** used for this layer.

- **`MEM0_INFER=false` (default)** — On each `add`, mem0 **embeds raw user/assistant messages** only. **No LLM calls** on write, so **zero** Gemini/OpenAI cost for memory. Retrieval stays embedding + vector search.
- **`MEM0_INFER=true`** — mem0 runs **fact extraction** via **Ollama** (`MEM0_OLLAMA_BASE_URL`, `MEM0_OLLAMA_MODEL`). Still **no** cloud API billing; you must run Ollama locally and `ollama pull` your chosen model.
- **Docker backend** — If the API runs in a container but Ollama stays on the host, set `MEM0_OLLAMA_BASE_URL=http://host.docker.internal:11434` (Windows/macOS). With `MEM0_INFER=false`, Ollama is not required at runtime.

### 3. LLM Resiliency & The Resiliency Manager
To handle `429 Resource Exhausted` errors and other API failures, the system uses a high-responsiveness **Resiliency Manager** (`apps/api/config.py`):

- **Fail-Fast Strategy**: The system is designed to **fail fast** (1 attempt/0 retries) for LLM operations. This allows the workflow to instantly trigger the **Raw Data Synthesis** fallback from the SQLite DB, ensuring the client receives their data without waiting for multi-minute retry windows.
- **Circuit Breaker**: If failures exceed a threshold or a hard quota is detected, the system enters a cooldown where all LLM calls are bypassed in favor of fallback paths.
- **Automated Persona Sync**: A dedicated ingestion script (`scripts/ingest_personas.py`) synchronizes JSON-based persona data into a centralized SQLite database, ensuring specialists have consistent access to local data mocks.
- **Graceful Fallbacks**:
    - **Tier 1 (Resiliency Mode)**: If Gemini is down/quota-exhausted, the system manually aggregates critical data (AUM, Balances) directly from the specialist outputs and SQLite to present the client with a "Service Alert" summary containing their actual banking figures. This is faster and more reliable than falling back to a local LLM.
    - **Local LLM Support (Ollama)**: While no longer the primary chat fallback, Ollama remains the core engine for **mem0 fact extraction** (if `MEM0_INFER=true`) and can be manually configured as the primary inference provider in `config.py`.

---

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
│   │   ├── memory/             mem0 + Redis (HF embeddings; Ollama for optional infer)
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
│       │   └── pages/          LoginPage, ChatPage, PerformancePage
├── rag/                        RAG pipeline + server
│   ├── pipeline/               Web and document scrapers (HTML cleaner, PDF parser, services scraper)
│   ├── ingest.py               PDF/DOCX/HTML → PostgreSQL pgvector (cosine similarity)
│   └── server.py               MCP server that queries pgvector for top-k chunks
├── data/                       Centralized Persona Database
│   └── persona.db              SQLite database for all customer data
├── mcp_servers/                Mock MCP servers (SQLite-backed)
├── docs/                       Source documents for RAG (PDF/DOCX)
├── scripts/
│   ├── ingest_personas.py      JSON → SQLite migration script
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

Ensure Postgres is running (`docker compose up -d postgres`), then initialize the RAG and Persona data:

```bash
# Ingest RAG documents
poe rag-ingestion

# Ingest/Reset Persona SQLite DB
python scripts/ingest_personas.py
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
| Memory        | mem0 + Redis (HF embeddings; Ollama optional for `MEM0_INFER`) |
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

## Application UI Features

- **Adjustable Sidebar** — Sidebar width can be dynamically adjusted by dragging its right edge, allowing for better readability of long chat titles. It can also be pinned or unpinned to maximize screen real estate.
- **Dark Mode Support** — Toggleable Light/Dark theme for comfortable viewing in any lighting condition.
- **Archived Chats** — Ability to hide or reveal archived chat sessions to keep the active workspace clutter-free.
- **Intelligent Prompting** — Suggested prompts in the empty state automatically trigger session creation when clicked, ensuring a seamless start to any conversation.

## Account Performance Page

A dedicated performance dashboard accessible via the **Account Performance** button in the sidebar. It provides an at-a-glance view of the client's portfolio with interactive charts, fully themed using the custom UBS Red & Grey branding palette.

### Features

- **Summary Cards** — Portfolio value, 6-month return, YTD return, and risk level displayed as key metric cards.
- **Net Worth Snapshot** — A comprehensive real-time net worth calculator dividing assets into Liquid & Cash Assets, Investment Portfolio (AUM), Real Estate, Business & Other Assets, and Liabilities. Includes an interactive visual completion bar representing the asset breakdown.
- **Portfolio Value Over Time** — Line chart tracking portfolio value across months with clickable data points.
- **Asset Allocation** — Interactive donut chart showing allocation across asset classes (Equities, Fixed Income, Private Equity, Hedge Funds, Structured Products, Real Assets & Cash).
- **Monthly Returns** — Bar chart displaying monthly gains/losses with positive (green/grey) and negative (red) bars.
- **Portfolio vs Benchmark** — Dual-line chart comparing portfolio performance against the S&P 500 benchmark.

### Insights & Opportunities

A proactive advisory section that analyzes the client's recent transaction history and account state to surface personalized financial suggestions.

- **Lifestyle-Based Signals** — Automatically detects significant events (e.g., luxury vehicle purchases, club memberships) and suggests relevant advisory actions (e.g., agreed-value insurance, lifestyle concierge).
- **Singapore Contextualization** — Signals are localized for the Singapore market, including **SRS/CPF** top-up reminders, **COE/ARF** management for vehicles, and tax-efficient reinvestment of dividends via **VCC** structures.
- **Cross-Border Advisory** — Provides guidance on complex regional investments, such as **Niseko property acquisition** with JPY-denominated financing.
- **Notify RM Flow** — A non-directive interaction model allowing users to send a pre-drafted, contextualized message to their Relationship Manager (Emma Clarke) for further discussion.

### Data Coherence (Singapore HNW Profile)

The application utilizes a coherent Singapore-based High Net Worth (HNW) profile for **John Smith (C-011)**. All financial data is standardized to **SGD** (e.g., **SGD 125M Net Worth**, **SGD 65M AUM**), featuring iconic Singaporean properties such as a **Sentosa Cove Villa** and a **Nassim Road GCB**. This ensures that both the visual dashboard and the agentic AI workflow operate on a consistent, localized factual foundation.

### Interactive Q&A

Clicking any data point on the charts (or an Insight signal) opens an inline **question panel**:
- **Chart Context** — Captures specific data points (e.g., "Oct return: +2.1%") for precise querying.
- **Insight Follow-up** — Allows direct notification of the Relationship Manager with one click via pre-drafted SGD-contextualized messages.
- **Unified Chat Session** — All performance-related questions are routed to a persistent "Account Performance Q&A" thread.

## Sample Queries

- **Greeting**: "Hello" (Direct response path)
- **Portfolio**: "How is my portfolio performing?" (Wealth Advisory → dashboard with charts)
- **Insights**: "What are my current wealth opportunities?" (Specialist agents assess Singapore-specific signals like SRS/CPF and VCC structures)
- **Market Outlook**: "What is the current macroeconomic outlook?" (Wealth Advisory → Tavily live search)
- **Multi-step**: "What's my balance and what are the current FX rates?" (Private Banking + FX Treasury)
- **RAG**: "What are the onboarding requirements for HNW clients in Singapore?" (Client Services + RAG)
- **Lending**: "What Lombard lending options are available for my SGD portfolio?" (Lending & Credit)
- **Performance Q&A**: Click a data point on the Account Performance page → "Why did my portfolio return -1.9% in Dec?" (routed to Wealth Advisory)

## Future Work

- Live portfolio data integration (replace mock data on Performance page)
- Streaming chart rendering as agent steps arrive
- Multi-currency portfolio view with live FX overlay
- PDF export of dashboard responses
- Persistent notification centre for RM escalations
