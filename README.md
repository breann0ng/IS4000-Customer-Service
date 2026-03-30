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
- [Data Service Layer](#data-service-layer)
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
                     │         ├── Knowledge      :9002 (uses Data Service)
                     │         ├── Service Wkflow :9003
                     │         └── RAG MCP        :9004
                     │
              ┌──────┼──────────────────────────┐
           Postgres  Redis           Data Service   LangSmith
        (sessions,   (mem0)          (Unified Mock  (tracing)
        pgvector RAG)                 JSON Loader)
```

**Escalation Check** inspects queries for high-distress or advisory intents (e.g., "What should I invest in?"), immediately bypassing the LLM workflow to return a static Relationship Manager response. All inputs are sanitized by the **Security Middleware**, which masks PII (NRIC, account numbers) and detects prompt injection attempts before they reach the LLM.

**Planner** analyzes the remaining client queries using Gemini 3.1 structured output and routes to one or more specialist agents. Simple greetings are handled via high-efficiency direct responses. **Executor** dispatches steps sequentially to the selected agents, each connected to MCP servers via Streamable HTTP. **Synthesizer** combines all agent outputs into a single polished response with follow-up suggestions and escalation flags.

All LLM calls use **Gemini structured outputs** (Pydantic models) for reliable parsing.

## Specialist Agents

| Agent                | MCP Server               | Responsibilities                                                                               |
| -------------------- | ------------------------ | ---------------------------------------------------------------------------------------------- |
| **Wealth Advisory**  | Banking Ops (:9001)      | Portfolio performance (YTD, 1Y, 24M), **Risk Metrics (Sharpe, Volatility, VAR)**, **Performance Attribution**, **Quantitative Market Insights (Tavily 5-result depth)** |
| **Private Banking**  | Knowledge (:9002)        | Account operations, fund transfers, statements, **Cross-border exposure analysis**, **Client preference management** |
| **Client Services**  | Service Workflow (:9003) | Onboarding, KYC/AML, **Service status tracking**, **Appointment scheduling**, **Tavily service context** |
| **Lending & Credit** | Banking Ops (:9001)      | **Tavily live mortgage/Lombard rates**, credit lines, LTV monitoring, **Covenant management** |
| **Compliance & Tax** | Knowledge (:9002)        | **Tax Loss Harvesting monitoring**, jurisdictions (CRS/FATCA), **KYC refresh workflows**, regulatory triggers |
| **FX & Treasury**    | Service Workflow (:9003) | **Tavily live foreign exchange rates**, currency hedging, FX derivatives, treasury management |

## Project Structure

```
├── apps/
│   ├── api/                    FastAPI backend
│   │   ├── auth/               LDAP authentication (mock) + JWT
│   │   ├── chat/               Chat session CRUD + message handling
│   │   ├── customers/          Customer performance & profile routes
│   │   │   ├── routes.py       API endpoint handlers
│   │   │   └── data_service.py **Centralized Data Service Layer**
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
│       │   └── pages/          LoginPage, ChatPage, PerformancePage
├── rag/                        RAG pipeline + server
│   ├── pipeline/               Web and document scrapers (HTML cleaner, PDF parser, services scraper)
│   ├── ingest.py               PDF/DOCX/HTML → PostgreSQL pgvector (cosine similarity)
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
| Live Search   | Tavily (**Intelligent Market-Contextualized Queries** for proactive advisory) |

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

## Advanced Wealth Analytics

The platform now supports high-fidelity financial metrics visible to all specialist agents:

- **Risk Management** — Real-time tracking of **Value-at-Risk (VAR)**, **Sharpe Ratio**, and **Portfolio Volatility**. Automated system triggers detect concentration risks and regulatory flags.
- **Market Insight Precision** — Wealth Advisory queries now utilize an increased **Tavily search depth (5 results)** and a **quantitative mandate** that requires specific market figures (e.g., actual index levels, Fed/ECB rate moves) in its analysis.
- **Performance Attribution** — Deeper analysis of returns categorized by **Selection Effect** and **Allocation Effect** relative to benchmarks.
- **Goal-Based Planning** — Structured tracking of client objectives (e.g., Wealth Preservation, Property Acquisition, Philanthropy) with automated liquidity and cashflow projections.
- **Tax Optimization** — Real-time monitoring of **Tax Loss Harvesting** buckets and localized tax slots (e.g., VCC, SRS/CPF) for tax-efficient reinvestment.

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

## Data Service Layer

To ensure 100% data coherence between the visual dashboard and the agentic chatbot, a centralized **Data Service** (`apps/api/customers/data_service.py`) acts as the single source of truth for **all client-specific data**.

- **Unified Loading** — Locates and globs mock JSON files in `mocks/customer_data/` based on `customer_id`.
- **SGD Defaulting** — All service layers and agent prompts are standardized to **SGD** (e.g., SGD 125M Net Worth, SGD 65M AUM) to ensure localized consistency for Singaporean HNWI clients.
- **Domain-Specific Contexts** — Provides tailored methods for `get_risk_analysis()`, `get_financial_planning()`, and `get_compliance_context()` ensuring high-fidelity data injection into agent prompts.
- **Dynamic Lending Context** — Combines real-time client limits with live market rates fetched via Tavily for personalized lending summaries.
- **Consistency Guarantee** — Any update to the mock JSON files is immediately reflected across all dashboard charts and AI agent responses.

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
