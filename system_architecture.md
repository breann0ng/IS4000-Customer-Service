# UBS Wealth Management Chatbot — System Design

The architecture is presented as five focused diagrams instead of one mega-diagram. Each can be read and explained on its own.

1. [System overview](#1-system-overview) — the three tiers end-to-end
2. [Frontend architecture](#2-frontend-architecture) — React app: pages, components, hooks, generated client
3. [Backend + workflow](#3-backend--workflow) — FastAPI routers, security middleware, LangGraph plan-and-execute, 6 agents
4. [RAG + MCP](#4-rag--mcp) — where grounded answers come from
5. [Infrastructure / DevOps](#5-infrastructure--devops) — containers, checks, observability

---

## 1. System overview

The 30-second view: three tiers, each only talking to its neighbours. Client → Backend → Data/AI.

```mermaid
graph LR
    subgraph CLIENT["🖥️ Client"]
        BROWSER["Browser<br/>React 19 + Vite + TS<br/>:3000 / :5173"]
    end

    subgraph BACKEND["⚙️ Backend"]
        API["FastAPI :8000<br/>auth · chat · customers · performance"]
        SEC["Security middleware<br/>PII mask · injection block"]
        WF["LangGraph workflow<br/>escalation → plan → execute → synth"]
        AGENTS["6 specialist agents"]
        API --> SEC --> WF --> AGENTS
    end

    subgraph DATA["💾 Data & AI"]
        PG[("PostgreSQL 16<br/>+ pgvector")]
        REDIS[("Redis<br/>mem0")]
        SQLITE[("SQLite<br/>customer profiles")]
        MCP["5 MCP servers<br/>:9001-:9005"]
        EXT["Gemini · Tavily<br/>· MiniLM-L6-v2"]
    end

    BROWSER -- "REST + SSE<br/>(JWT)" --> API
    AGENTS -- "JSON-RPC" --> MCP
    AGENTS -- "structured calls" --> EXT
    WF --> PG
    WF --> REDIS
    MCP --> PG
    MCP --> SQLITE
    MCP --> EXT

    classDef client fill:#dbeafe,stroke:#1e40af,color:#000
    classDef backend fill:#fecaca,stroke:#b91c1c,color:#000
    classDef data fill:#fde68a,stroke:#b45309,color:#000
    class BROWSER client
    class API,SEC,WF,AGENTS backend
    class PG,REDIS,SQLITE,MCP,EXT data
```

**Request lifecycle**

1. Browser sends a question over REST + SSE with a JWT.
2. FastAPI runs the security middleware (PII mask, injection check).
3. The LangGraph workflow plans the work, runs specialist agents in parallel, and synthesises one reply.
4. Each agent calls its MCP server for tool-use, and may pull grounded context from RAG and live data from Tavily.
5. The reply streams back as SSE; the user message and assistant reply are persisted in Postgres, with conversation context saved to Redis (mem0).

---

## 2. Frontend architecture

React app. Pages render components, components use hooks, hooks talk to a TypeScript client that is auto-generated from the backend's OpenAPI schema.

```mermaid
graph TB
    BROWSER[["Browser<br/>:3000 / :5173"]]

    subgraph PAGES["Pages"]
        LOGIN[LoginPage]
        CHAT[ChatPage<br/>SSE streaming]
        PERF[PerformancePage<br/>charts + insights]
    end

    subgraph COMPS["Components"]
        SIDEBAR[Sidebar<br/>archive · pin · rename]
        CHAT_WIN[ChatWindow]
        BUBBLE[MessageBubble]
        THINK[ThinkingIndicator<br/>planning ▸ agent_step ▸<br/>synthesizing ▸ done]
        STRUCT[StructuredMessage<br/>parses dashboard JSON]
        CHART[ChartCard<br/>SVG pie / bar / line]
    end

    subgraph HOOKS["Hooks"]
        STREAM[useMessageStream<br/>EventSource SSE]
        AUTH[useAuth — JWT]
        FILE[useFileUpload]
        THEME[useTheme]
    end

    APIGEN[/"src/api/generated/<br/>auto-gen TS client<br/>← openapi.json"/]

    BROWSER --> PAGES
    PAGES --> COMPS
    COMPS --> HOOKS
    HOOKS --> APIGEN
    APIGEN -- "fetch / EventSource" --> BACKEND[("FastAPI :8000")]

    classDef page fill:#dbeafe,stroke:#1e40af,color:#000
    classDef comp fill:#d9f99d,stroke:#3f6212,color:#000
    classDef hook fill:#fbcfe8,stroke:#9d174d,color:#000
    classDef gen fill:#fde68a,stroke:#b45309,color:#000
    class LOGIN,CHAT,PERF page
    class SIDEBAR,CHAT_WIN,BUBBLE,THINK,STRUCT,CHART comp
    class STREAM,AUTH,FILE,THEME hook
    class APIGEN gen
```

**Key idea — no drift.** The backend exports `openapi.json` on every change; `scripts/check_openapi_drift.py` enforces in CI that the committed schema matches the live app. The TypeScript client in `src/api/generated/` is regenerated from that schema, so the frontend cannot drift from the API contract.

**SSE phases the UI renders.** As the workflow runs, the `ThinkingIndicator` shows `planning ▸ agent_step ▸ synthesizing ▸ done` based on events streamed from the backend.

---

## 3. Backend + workflow

FastAPI receives the request and runs the LangGraph plan-and-execute pipeline.

```mermaid
graph TB
    REQ[/"POST /sessions/{id}/<br/>messages/stream"/]

    subgraph API["⚙️ FastAPI — apps/api"]
        MAIN["main.py<br/>CORS · Lifespan · Scalar /docs"]

        subgraph ROUTES["Routers"]
            R_AUTH["auth/<br/>LDAP mock + JWT"]
            R_CHAT["chat/<br/>routes · service · models<br/>rm_intake · followups"]
            R_CUST["customers/<br/>360 view"]
            R_PERF["performance/<br/>dashboard data"]
        end

        SEC["🛡️ security/input_guard.py<br/>NRIC + account masking<br/>15 injection patterns"]

        subgraph WF["🧠 LangGraph workflow"]
            ESC["escalation.py<br/>regex matrix<br/>→ static RM reply"]
            PLAN["planner.py<br/>Gemini structured<br/>greeting fast-path"]
            EXEC["executor.py<br/>asyncio.gather<br/>parallel dispatch"]
            SYN["graph.py · synthesizer<br/>merges agent outputs<br/>+ follow-ups"]
            STATE["state.py<br/>WorkflowState (Pydantic)"]
            ESC --> PLAN --> EXEC --> SYN
            STATE -.shared.- PLAN
            STATE -.shared.- EXEC
            STATE -.shared.- SYN
        end

        subgraph AGENTS["👥 6 specialist agents"]
            A_WEALTH[Wealth Advisory]
            A_PRIV[Private Banking]
            A_CS[Client Services]
            A_LEND[Lending & Credit]
            A_COMP[Compliance & Tax]
            A_FX[FX & Treasury]
        end

        DB["database/<br/>SQLAlchemy async<br/>users · sessions · messages · documents"]
        MEM["memory/mem0_client.py<br/>short-term context"]
    end

    REQ --> MAIN
    MAIN --> ROUTES
    R_CHAT --> SEC
    SEC --> ESC
    PLAN --> A_WEALTH & A_PRIV & A_CS & A_LEND & A_COMP & A_FX
    A_WEALTH & A_PRIV & A_CS & A_LEND & A_COMP & A_FX --> EXEC
    SYN -- "SSE phases" --> R_CHAT
    R_CHAT -- "save_message" --> DB
    R_CHAT -- "store_memory" --> MEM

    classDef sec fill:#fecaca,stroke:#b91c1c,color:#000
    classDef wf fill:#fbcfe8,stroke:#9d174d,color:#000
    classDef agent fill:#d9f99d,stroke:#3f6212,color:#000
    class SEC sec
    class ESC,PLAN,EXEC,SYN,STATE wf
    class A_WEALTH,A_PRIV,A_CS,A_LEND,A_COMP,A_FX agent
```

**Specialist-agent → MCP routing**

| Agent | MCP backend |
|---|---|
| Wealth Advisory | Banking Ops :9001 |
| Lending & Credit | Banking Ops :9001 |
| Private Banking | Knowledge :9002 |
| Compliance & Tax | Knowledge :9002 |
| Client Services | Service Workflow :9003 |
| FX & Treasury | Service Workflow :9003 |
| *(all)* | RAG :9004 (grounding) · Customer Data :9005 (context) |

**Why this shape works.** The escalation node is a hard regex gate — anything advisory or distress-flagged bypasses the LLM entirely. The planner returns a Pydantic-validated `Plan` object (no free-form parsing). The executor uses `asyncio.gather`, so a slow agent does not block the others. The synthesizer is the only place the final response is composed.

---

## 4. RAG + MCP

Where grounded answers come from. Agents do not trust the LLM's memory — they call MCP servers, which look things up in real data.

```mermaid
graph TB
    subgraph AGENTS["6 specialist agents"]
        ALL_AGENTS[Wealth · Private Banking<br/>Client Services · Lending<br/>Compliance · FX]
    end

    subgraph MCP["🔌 MCP servers — Streamable HTTP / JSON-RPC"]
        MCP_BANK["Banking Ops :9001<br/>wealth_advisory ·<br/>lending_credit ·<br/>banking_operation"]
        MCP_KNOW["Knowledge :9002<br/>private_banking ·<br/>compliance_tax ·<br/>knowledge_query"]
        MCP_SVC["Service Workflow :9003<br/>client_services ·<br/>fx_treasury ·<br/>service_workflow"]
        MCP_RAG["RAG :9004<br/>retrieve_documents"]
        MCP_CUST["Customer Data :9005<br/>customer_get_360 / _summary /<br/>_transactions / _profile"]
    end

    subgraph DATA["Data + external"]
        PG[("PostgreSQL<br/>pgvector 384-dim<br/>cosine top-k")]
        SQLITE[("SQLite<br/>data/customer_data.db<br/>C-001 · C-002 · C-003")]
        GEMINI["Google Gemini 3.1<br/>structured outputs"]
        TAVILY["Tavily<br/>live FX · rates · markets"]
        HF["MiniLM-L6-v2<br/>(local embeddings)"]
    end

    MCP_CLIENT["tools/mcp_client.py<br/>JSON-RPC 2.0 over HTTP"]
    RAG_TOOL["tools/rag_tool.py<br/>retrieve_rag_chunks(top_k)"]

    ALL_AGENTS --> MCP_CLIENT
    ALL_AGENTS -. "RAG context" .-> RAG_TOOL --> MCP_RAG

    MCP_CLIENT --> MCP_BANK & MCP_KNOW & MCP_SVC & MCP_CUST

    MCP_BANK -. "retrieve_documents" .-> MCP_RAG
    MCP_KNOW -. "retrieve_documents" .-> MCP_RAG
    MCP_SVC  -. "retrieve_documents" .-> MCP_RAG

    MCP_BANK & MCP_KNOW & MCP_SVC --> GEMINI
    MCP_BANK -- "rates / markets" --> TAVILY
    MCP_SVC  -- "FX" --> TAVILY

    MCP_RAG -- "cosine top-k" --> PG
    MCP_RAG -- "embed query" --> HF
    MCP_CUST --> SQLITE

    classDef mcp fill:#e9d5ff,stroke:#6b21a8,color:#000
    classDef store fill:#bae6fd,stroke:#0369a1,color:#000
    classDef ext fill:#fde68a,stroke:#b45309,color:#000
    class MCP_BANK,MCP_KNOW,MCP_SVC,MCP_RAG,MCP_CUST mcp
    class PG,SQLITE store
    class GEMINI,TAVILY,HF ext
```

### MCP tool inventory

| MCP server | Port | Exposed tools |
|---|---|---|
| Banking Ops | 9001 | `wealth_advisory`, `lending_credit`, `banking_operation` |
| Knowledge | 9002 | `private_banking`, `compliance_tax`, `knowledge_query` |
| Service Workflow | 9003 | `client_services`, `fx_treasury`, `service_workflow` |
| RAG | 9004 | `retrieve_documents` |
| Customer Data | 9005 | `customer_get_360`, `customer_get_summary`, `customer_get_transactions`, `customer_get_profile` |

### RAG ingestion (offline)

Documents become searchable chunks before they can ground an answer.

```mermaid
graph LR
    DOCS_SRC[/"docs/<br/>PDF · DOCX · HTML"/]
    SCRAPERS["pipeline/scrapers/<br/>services_scraper · help_scraper · pdf_scraper"]
    PROC["pipeline/processors/<br/>html_cleaner · chunker"]
    INGEST["ingest.py<br/>+ pipeline/run_all.py<br/>+ ingest_to_chroma.py"]
    HF["MiniLM-L6-v2<br/>(local)"]
    PG[("PostgreSQL<br/>pgvector")]

    DOCS_SRC --> SCRAPERS --> PROC --> INGEST
    INGEST -- "embed" --> HF
    INGEST -- "upsert" --> PG

    classDef store fill:#bae6fd,stroke:#0369a1,color:#000
    class PG store
```

**Customer data is MCP-fronted by default.** API routes call `customer_get_360` on `:9005`; the same SQLite bundle backs the dashboard and the workflow, so the chatbot and the Performance page never disagree. `CUSTOMER_DATA_ACCESS_MODE=direct` lets the API fall back to reading SQLite directly for local troubleshooting.

---

## 5. Infrastructure / DevOps

```mermaid
graph TB
    subgraph RUN["🚀 Run"]
        DOCKER["docker-compose.yml<br/>postgres · redis · 4 mock MCPs ·<br/>rag-server · backend · frontend"]
        POE["pyproject.toml (poe)<br/>dev-api · dev-ui · mock-mcp ·<br/>rag-server · rag-ingestion · seed-customers"]
        SCRIPTS["scripts/<br/>seed_customer_data ·<br/>export_openapi · check_openapi_drift"]
        MOCKS["mocks/<br/>banking_ops · knowledge ·<br/>service_workflow stubs"]
    end

    subgraph VERIFY["✅ Verify"]
        HOOKS_GIT["lefthook.yml<br/>pre-commit"]
        RUFF["ruff<br/>format + lint"]
        TY["ty<br/>type-check"]
        DRIFT["check_openapi_drift<br/>schema must match"]
        TESTS["tests/<br/>chat_followups · rm_intake"]
        HOOKS_GIT --> RUFF & TY & DRIFT
    end

    subgraph OBSERVE["🔍 Observe"]
        LOGS["structured JSON logs<br/>logging_config.py"]
        LANGSMITH["LangSmith<br/>tracing (optional)"]
        SSE_EVT["SSE phase events<br/>visible in UI"]
        SEC_EVT["security audit events<br/>pii_masked ·<br/>prompt_injection_detected ·<br/>escalation_triggered"]
    end

    DOCKER -.spins up.-> SERVICES[("backend ·<br/>frontend ·<br/>postgres · redis ·<br/>5 MCP servers")]
    POE --> SCRIPTS
    SCRIPTS -. seed .-> SQLITE[("SQLite")]
    SCRIPTS -. drift .-> APIGEN["TS client"]
    HOOKS_GIT -. blocks merge .-> POE

    classDef run fill:#dbeafe,stroke:#1e40af,color:#000
    classDef verify fill:#d9f99d,stroke:#3f6212,color:#000
    classDef observe fill:#fde68a,stroke:#b45309,color:#000
    class DOCKER,POE,SCRIPTS,MOCKS run
    class HOOKS_GIT,RUFF,TY,DRIFT,TESTS verify
    class LOGS,LANGSMITH,SSE_EVT,SEC_EVT observe
```

### Environments

| Mode | Command | What you get |
|---|---|---|
| Full stack | `docker compose up` | Postgres + Redis + 5 MCP servers + RAG + backend + frontend |
| Hot-reload dev | `poe dev-api` + `poe dev-ui` + `poe mock-mcp` + `poe rag-server` | Same surface, individual processes |
| Data reset | `poe seed-customers` | Rebuild SQLite from approved profiles |
| RAG reset | `poe rag-ingestion` | Re-embed and re-upsert documents to pgvector |

### Quality gates

- **Lefthook pre-commit** — runs `ruff format`, `ruff lint`, `ty` type-check, and OpenAPI drift check before any commit lands.
- **OpenAPI as the contract** — backend exports `openapi.json`; the TypeScript client is regenerated from it; CI fails if the committed schema diverges from the live app.
- **Pydantic everywhere** — every LLM call returns a typed object; schema-validation failures fail closed, never silently.
- **Tests** — `pytest` covers the chat follow-up flow and the RM-intake escalation flow.

### Observability

- **Structured logs** — every service emits JSON with consistent keys.
- **LangSmith traces** — optional, on planner / executor / synthesizer for post-incident replay.
- **UI thinking indicator** — `planning ▸ agent_step ▸ synthesizing ▸ done` visible to the user, drawn from real workflow events.
- **Security events** — `pii_masked`, `prompt_injection_detected`, `escalation_triggered` are all audit-tagged.
