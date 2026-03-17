# UBS Customer Service Chatbot

AI-powered customer service chatbot for UBS Wealth Management, serving High Net Worth Individual (HNWI) clients. Built with a LangGraph plan-and-execute agentic workflow, FastAPI backend, and React frontend.

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
                     │         ├── Banking Ops    :9001 (mock)
                     │         ├── Knowledge      :9002 (mock)
                     │         ├── Service Wkflow :9003 (mock)
                     │         └── RAG Server     :9004 (real ChromaDB)
                     │
              ┌──────┼──────────┐
           Postgres  Redis    ChromaDB
           (sessions)(mem0)   (RAG vectors)
```

**Planner** analyzes each client query using Gemini structured output and routes to one or more specialist agents. **Executor** dispatches steps sequentially to the selected agents, each connected to MCP servers via Streamable HTTP. **Synthesizer** combines all agent outputs into a single polished response with follow-up suggestions and escalation flags.

All LLM calls use **Gemini structured outputs** (Pydantic models enforced at the API level) for reliable parsing.

## Specialist Agents

| Agent | MCP Server | Responsibilities |
|---|---|---|
| **Wealth Advisory** | Banking Ops (:9001) | Portfolio performance, investment strategy, market insights, asset allocation, estate planning |
| **Private Banking** | Knowledge (:9002) | Account operations, fund transfers, card services, statements, multi-currency management |
| **Client Services** | Service Workflow (:9003) | Onboarding, KYC/AML, document requests, appointments, escalations (uses RAG) |
| **Lending & Credit** | Banking Ops (:9001) | Lombard lending, mortgages, credit lines, structured lending, margin facilities |
| **Compliance & Tax** | Knowledge (:9002) | CRS/FATCA reporting, cross-border tax, regulatory updates, documentation (uses RAG) |
| **FX & Treasury** | Service Workflow (:9003) | Foreign exchange, currency hedging, FX derivatives, treasury management |

## Project Structure

```
├── apps/
│   ├── api/                    FastAPI backend
│   │   ├── auth/               LDAP authentication (mock) + JWT
│   │   ├── chat/               Chat session CRUD + message handling
│   │   ├── database/           SQLAlchemy async models (Postgres)
│   │   ├── memory/             mem0 + Redis short-context memory (HuggingFace embeddings)
│   │   ├── workflow/           LangGraph agentic workflow
│   │   │   ├── agents/         6 specialist agents
│   │   │   ├── tools/          MCP client + RAG retrieval tool
│   │   │   ├── planner.py      Structured plan generation (Gemini)
│   │   │   ├── executor.py     Agent dispatch loop
│   │   │   ├── graph.py        StateGraph definition + synthesizer
│   │   │   └── state.py        Pydantic state/output models
│   │   ├── config.py           Pydantic Settings (.env)
│   │   ├── logging_config.py   structlog + OpenTelemetry trace context
│   │   └── main.py             App entrypoint + Scalar API docs
│   └── ui/                     React + TypeScript frontend (Vite)
│       ├── openapi.json         Committed OpenAPI schema (auto-generated)
│       └── src/
│           ├── api/
│           │   ├── generated/   Auto-generated TypeScript client (@hey-api/openapi-ts)
│           │   └── client.ts    Client configuration (base URL, auth interceptor)
│           ├── components/      Sidebar, ChatWindow, MessageBubble, ThinkingIndicator
│           ├── hooks/           useAuth, useTheme, useMessageStream, useLlmMode
│           └── pages/           LoginPage, ChatPage
├── rag/                        RAG pipeline + server
│   ├── config.py               Pipeline settings
│   ├── ingest.py               PDF/DOCX → ChromaDB (cosine similarity)
│   └── server.py               MCP server that queries ChromaDB for top-k chunks
├── mocks/                      Mock MCP servers for local development
│   ├── base.py                 Shared JSON-RPC handler factory
│   ├── banking_ops_server.py   Mock banking ops + wealth advisory + lending (:9001)
│   ├── knowledge_server.py     Mock private banking + compliance + knowledge (:9002)
│   └── service_workflow_server.py  Mock client services + FX treasury (:9003)
├── docs/                       Source documents for RAG (place PDFs/DOCX here)
├── models/                     Auto-downloaded embedding models (gitignored)
├── tests/
├── scripts/
│   ├── export_openapi.py       Export OpenAPI JSON from FastAPI app
│   └── check_openapi_drift.py  CI check: committed schema matches live app
├── pyproject.toml              Dependencies + poe tasks
├── uv.lock                     Locked dependencies
├── Dockerfile                  Multi-stage: backend + frontend
├── docker-compose.yml          All services (Postgres, Redis, mocks, RAG, backend, frontend)
├── .env.example                Environment variable template
└── .gitignore
```

## Prerequisites

### Python 3.12+

Verify with:

```bash
python3 --version
```

### uv (Python package manager)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Verify with:

```bash
uv --version
```

### Node.js 22+ and pnpm

Required for the React frontend. Install via [nvm](https://github.com/nvm-sh/nvm):

```bash
# install nvm
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.4/install.sh | bash

# load nvm into your current shell (or just open a new terminal)
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

# install Node.js 22
nvm install 22

# verify
node --version
```

Install pnpm:

```bash
curl -fsSL https://get.pnpm.io/install.sh | sh -

# verify
pnpm --version
```

### Docker and Docker Compose

Required for running Postgres, Redis, and production builds.

```bash
# Install Docker Engine (Ubuntu/WSL2)
# https://docs.docker.com/engine/install/ubuntu/

# Verify
docker --version
docker compose version
```

### Gemini API Key (optional)

Obtain from [Google AI Studio](https://aistudio.google.com/apikey). If no key is configured, the workflow runs in **mock mode** — the planner and synthesizer return canned responses so you can develop and test the full stack without an API key.

## Getting Started

### 1. Install dependencies

```bash
cd ubs-project
uv sync
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and optionally set your `GEMINI_API_KEY`. Without it the chatbot runs in mock mode. Everything else has working defaults for local development.

### 3. Start infrastructure (Postgres + Redis)

```bash
docker compose up -d postgres redis
```

### 4. Install frontend dependencies

```bash
cd apps/ui
pnpm install
cd ../..
```

### 5. Start mock MCP servers + RAG server

```bash
# terminal 1: mock MCP servers (banking ops, knowledge, service workflow)
poe mock-mcp

# terminal 2: RAG server (queries ChromaDB)
poe rag-server
```

### 6. Run the backend

```bash
# terminal 3
poe dev-api
```

The API is available at `http://localhost:8000`. Scalar API reference at `http://localhost:8000/docs`.

### 7. Run the frontend

```bash
# terminal 4
poe dev-ui
```

The UI is available at `http://localhost:5173`. The Vite dev server proxies `/api` requests to the backend.

### 8. Login

Use one of the mock LDAP credentials:

| Username | Password | Name |
|---|---|---|
| `jsmith` | `password123` | John Smith |
| `ajones` | `password123` | Alice Jones |
| `bwilson` | `password123` | Bob Wilson |

## Docker (Full Stack)

Build and run everything with a single command (Postgres, Redis, 3 mock MCP servers, RAG server, backend, frontend):

```bash
poe docker-up
```

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| Scalar API Reference | http://localhost:8000/docs |
| Mock Banking Ops MCP | http://localhost:9001 |
| Mock Knowledge MCP | http://localhost:9002 |
| Mock Service Workflow MCP | http://localhost:9003 |
| RAG MCP Server | http://localhost:9004 |

Tear down (including volumes):

```bash
poe docker-down
```

## RAG Document Ingestion

Place PDF or DOCX files in the `docs/` directory, then run:

```bash
poe rag-ingestion
```

This will:
1. Extract text from all PDF (via PyMuPDF) and DOCX files
2. Chunk the text (configurable `chunk_size` and `chunk_overlap`)
3. Download the embedding model on first run (saved to `models/`, no HuggingFace token required)
4. Generate embeddings using `sentence-transformers/all-MiniLM-L6-v2`
5. Store vectors in ChromaDB with cosine similarity search

> PyTorch is configured to install from the CPU-only index via `pyproject.toml` (`[tool.uv.sources]`), avoiding the ~5GB CUDA download.

The RAG MCP server (`poe rag-server`) then serves these chunks to the Client Services and Compliance & Tax agents at query time.

Configure via environment variables or `.env`:

| Variable | Default | Description |
|---|---|---|
| `EMBEDDING_MODEL_NAME` | `sentence-transformers/all-MiniLM-L6-v2` | HuggingFace embedding model |
| `CHROMA_PERSIST_DIRECTORY` | `./data/chroma` | ChromaDB storage path |
| `RAG_TOP_K` | `5` | Number of chunks to retrieve per query |

## Development Tasks

All tasks are run via [poethepoet](https://poethepoet.naber.dev/) (`uv run poe <task>`):

| Task | Description |
|---|---|
| `poe dev-api` | Start the FastAPI backend with hot reload on port 8000 |
| `poe dev-ui` | Start the React frontend dev server on port 5173 |
| `poe generate-api-client` | Export OpenAPI schema and regenerate TypeScript client |
| `poe check` | Format, lint, type-check Python code, and check for OpenAPI drift |
| `poe mock-mcp` | Start all 3 mock MCP servers (:9001, :9002, :9003) |
| `poe rag-server` | Start the RAG MCP server that queries ChromaDB on port 9004 |
| `poe rag-ingestion` | Ingest documents from docs/ into ChromaDB vector store |
| `poe docker-up` | Build and start all services via Docker Compose |
| `poe docker-down` | Stop and remove all Docker services and volumes |

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/auth/login` | Authenticate via LDAP, returns JWT |
| `GET` | `/api/auth/me` | Get current user profile |
| `POST` | `/api/chat/sessions` | Create a new chat session |
| `GET` | `/api/chat/sessions` | List sessions (optionally include archived) |
| `GET` | `/api/chat/sessions/{id}` | Get session with full message history |
| `PATCH` | `/api/chat/sessions/{id}` | Rename or archive a session |
| `DELETE` | `/api/chat/sessions/{id}` | Permanently delete a session |
| `POST` | `/api/chat/sessions/{id}/messages` | Send a message, receive AI response |
| `POST` | `/api/chat/sessions/{id}/messages/stream` | Send a message, receive SSE stream with thinking steps |
| `GET` | `/api/health` | Health check (includes `llm_mode: "mock" \| "live"`) |

All request and response bodies are strictly validated with Pydantic models. The Scalar API reference is available at `/docs`.

## API Client Generation

The TypeScript frontend uses an auto-generated API client — no manual `fetch` calls or hand-written types. The pipeline:

1. `scripts/export_openapi.py` extracts the OpenAPI schema from the FastAPI app into `apps/ui/openapi.json`
2. `@hey-api/openapi-ts` generates a fully-typed TypeScript SDK in `apps/ui/src/api/generated/`
3. Components import generated functions and types directly — full autocomplete and compile-time safety

To regenerate after changing any API endpoint or Pydantic model:

```bash
poe generate-api-client
```

The `poe check` task includes an OpenAPI drift check that fails if the committed `openapi.json` doesn't match the current FastAPI schema, preventing stale clients from reaching production.

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `GEMINI_API_KEY` | No | — | Google Gemini API key (mock mode if unset) |
| `GEMINI_MODEL` | No | `gemini-2.0-flash-lite` | Gemini model identifier |
| `DATABASE_URL` | No | `postgresql+asyncpg://postgres:postgres@localhost:5432/chatbot` | Postgres connection string |
| `REDIS_URL` | No | `redis://localhost:6379/0` | Redis connection string |
| `JWT_SECRET_KEY` | Yes (production) | `change-me-to-a-secure-random-string` | Secret for JWT signing |
| `LOG_LEVEL` | No | `INFO` | Logging level |
| `MCP_BANKING_OPS_URL` | No | `http://localhost:9001/mcp` | Banking ops MCP server |
| `MCP_KNOWLEDGE_URL` | No | `http://localhost:9002/mcp` | Knowledge MCP server |
| `MCP_SERVICE_WORKFLOW_URL` | No | `http://localhost:9003/mcp` | Service workflow MCP server |
| `MCP_RAG_SERVER_URL` | No | `http://localhost:9004/mcp` | RAG retrieval MCP server |
| `RAG_TOP_K` | No | `5` | Number of RAG chunks to retrieve |

## Tech Stack

| Layer | Technology |
|---|---|
| LLM | Google Gemini (structured outputs) |
| Orchestration | LangGraph (plan-and-execute) |
| Backend | FastAPI, Pydantic, SQLAlchemy (async) |
| Frontend | React 19, TypeScript, Vite, Radix UI, @hey-api/openapi-ts |
| API Docs | Scalar |
| Database | PostgreSQL 16 (sessions, messages as JSONB) |
| Memory | mem0 + Redis (HuggingFace local embeddings) |
| Vector Store | ChromaDB (cosine similarity) |
| Embeddings | sentence-transformers (HuggingFace, local) |
| Document Processing | PyMuPDF (PDF), python-docx (DOCX) |
| Tool Integration | MCP (Streamable HTTP) |
| Logging | structlog + OpenTelemetry trace context |
| Auth | Mock LDAP + JWT |
| Package Manager | uv (Python), pnpm (Node.js) |
| Code Quality | ruff (format + lint) + ty (type check) via uvx |
| Containerization | Docker + Docker Compose |

## Streaming & Thinking Steps

The UI streams responses in real time via Server-Sent Events (SSE), showing intermediate thinking steps as the workflow progresses — similar to ChatGPT's reasoning display.

When a message is sent, the frontend connects to `/api/chat/sessions/{id}/messages/stream` and receives events:

1. **`planning`** — The planner's reasoning and the list of agents/tasks it has routed to
2. **`agent_step`** — Each specialist agent's result as it completes (with a progress counter)
3. **`synthesizing`** — Indicates the synthesizer is composing the final response
4. **`done`** — The final persisted message, at which point the thinking indicator clears and the response renders

The thinking panel is collapsible and shows checkmarks for completed steps, spinners for active steps, and intermediate result snippets.

### Mock vs Live Mode

The `/api/health` endpoint returns `llm_mode: "mock"` or `llm_mode: "live"`. When running in mock mode (no `GEMINI_API_KEY`), the UI displays a yellow **MOCK MODE** badge at the bottom of the chat window. In live mode, the planner and synthesizer use Gemini structured outputs for real routing and response generation.

## Sample Queries

Use these queries to exercise the different agents and workflow paths.

### Single-Agent Queries

| Query | Routes to | Expected response |
|---|---|---|
| "How is my portfolio performing?" | Wealth Advisory | Portfolio overview with AUM (CHF 12.4M), asset allocation breakdown, YTD performance (+6.8%) |
| "What are my account balances?" | Private Banking | 4 accounts across CHF/EUR/USD/GBP with balances totaling CHF 7.49M |
| "I need to schedule an appointment with my relationship manager" | Client Services | Service request with reference number (CS-XXXXXX), 2-3 business day timeline, required documents |
| "What Lombard lending options do I have?" | Lending & Credit | Credit line at SARON + 0.85%, mortgage rates (fixed 5yr: 1.35%, 10yr: 1.45%), LTV details |
| "Am I compliant with CRS and FATCA reporting?" | Compliance & Tax | Compliance status (fully compliant), KYC review dates, CRS deadline (30 June 2026) |
| "What's the current EUR/CHF exchange rate?" | FX & Treasury | FX rates for 6 currency pairs with bid/ask spreads and daily changes |

### Multi-Agent Queries

These are the most interesting for testing the streaming thinking indicator, as you'll see multiple steps progress in sequence.

| Query | Expected routing | Why |
|---|---|---|
| "I want to transfer EUR 500k to my CHF account — what rate can I get?" | FX & Treasury + Private Banking | FX rates then account details |
| "Review my portfolio and check what lending options I have against it" | Wealth Advisory + Lending & Credit | Portfolio review then Lombard assessment |
| "I'm relocating to Singapore — what are the tax implications and can you help with the paperwork?" | Compliance & Tax + Client Services | CRS/FATCA impact then onboarding docs (both use RAG) |
| "What's my total net worth across all accounts and investments?" | Private Banking + Wealth Advisory | Account balances + portfolio AUM |

### Direct Response (No Agent Routing)

| Query | What happens |
|---|---|
| "Hello" | Planner sets `requires_agent: false`, returns a greeting directly — no executor or synthesizer steps |
| "Thank you" | Direct response, no agents invoked |

### What to Watch in the UI

- **Planning phase**: The planner's reasoning text and the step list with agent names and tasks
- **Execution phase**: Each step completes one at a time — checkmark appears, intermediate result snippet shows
- **Synthesizing phase**: Spinner while the synthesizer combines all agent outputs into a polished response
- **Final response**: Thinking indicator clears and the synthesized message renders
- **Mock badge**: Yellow "MOCK MODE" pill confirms canned responses when no Gemini key is set

## Future Work

The current setup is optimized for quick local bootstrapping. The following items would be needed to turn this into a production-grade live application.

### Database Migrations

Replace the `create_all` auto-DDL with **Alembic** migrations. The current approach recreates tables on startup and tears down Postgres between runs, which is fine for local dev but loses data and prevents schema evolution. Alembic would provide versioned, reviewable migration files and safe rollback.

### Authentication & Authorization

Replace the mock LDAP stub with a real identity stack. Integrate with corporate **LDAP/Active Directory** for user authentication and add **Authelia** (or similar) as an SSO/MFA gateway in front of the application. Implement proper role-based access control (RBAC) so different user tiers (e.g., relationship managers vs. clients) see different capabilities.

### Durable Workflow Execution

For production workloads, consider migrating the LangGraph agentic workflow to **Temporal** for durable execution. The current in-process workflow has no fault tolerance — if the API server restarts mid-request, the workflow is lost. Temporal provides automatic retries, timeouts, and resumability at each step, which is critical for long-running multi-agent queries that may involve real banking operations. Each agent step (planner, executor dispatch, synthesizer) would become a Temporal activity with its own retry policy, and the overall plan-and-execute loop would be a Temporal workflow with full observability via the Temporal UI. This also enables workflow versioning for safe rollouts and replay-based debugging of production incidents.
  
### Kubernetes Deployment

Move from Docker Compose to **Kubernetes** for production orchestration. This includes Helm charts or Kustomize overlays for all services (API, UI, MCP servers, RAG server), horizontal pod autoscaling for the API and workflow workers, health/readiness probes, and a proper ingress controller (e.g., nginx-ingress or Traefik) with TLS termination.

### Cloud Infrastructure (AWS + Terraform)

Host the full stack on **AWS** with infrastructure managed by **Terraform**:

- **EKS** for the Kubernetes cluster
- **RDS (PostgreSQL)** for persistent sessions/messages with automated backups
- **ElastiCache (Redis)** for mem0 short-term memory
- **S3** for RAG document storage and ChromaDB persistence
- **ALB** + **Route 53** for load balancing and DNS
- **ECR** for container image registry
- **Secrets Manager** for API keys and JWT secrets
- **CloudWatch** / **OpenTelemetry Collector** for centralized logging and tracing

### Observability

Expand the existing structlog + OpenTelemetry setup into a full observability stack: ship traces to **Jaeger** or **Tempo**, metrics to **Prometheus** + **Grafana**, and structured logs to **Loki** or **CloudWatch Logs**. Add dashboards for LLM latency, token usage, agent success rates, and MCP server health.

### Internal MCP Servers

Replace the mock MCP servers with connections to real internal systems. The current mock servers (`banking_ops`, `knowledge`, `service_workflow`) return canned responses — in production these would point to actual internal APIs exposing real banking operations, client data, and workflow engines. This involves updating the `MCP_*_URL` environment variables to internal endpoints, handling mutual TLS or OAuth2 client credentials for service-to-service auth, and adapting the tool schemas if the real servers expose different capabilities than the mocks.

### CI/CD Pipeline

Set up **GitHub Actions** (or similar) with stages for lint/type-check (`poe check`), unit/integration tests, OpenAPI drift detection, container image build + push, and automated deployment to staging/production Kubernetes environments.
