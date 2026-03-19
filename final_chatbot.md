# Final Private Banking AI Chatbot — Architecture & Master Specification

> **Principal AI Architect Review** | Consolidated Strategy based on Gemini POV, Perplexity POV, and KIM Architecture.
> This document serves as the final, approved blueprint for building the UBS/High-Net-Worth Private Banking AI Assistant.

---

## 1. Project Vision & Core Philosophy

**Dual-Role "Power-Assistant"**
The AI acts as a 24/7 technical concierge for the High-Net-Worth Individual (HNWI) and a proactive Co-Pilot for the Relationship Manager (RM). It does **not** replace the RM. It strictly operates within an *informational* boundary, aggressively escalating *advisory* or *transactional* requests to human RMs.

**Key Mandates:**
*   **Zero-Trust Integration:** The LLM never touches raw core banking data directly. All access is brokered via standardized Model Context Protocol (MCP) servers.
*   **Deterministic Outputs:** Strict enforcement of LLM outputs using PydanticAI structured generation to prevent hallucinatory UI rendering.
*   **Compliance-First:** Built from day one to meet MAS FEAT principles, EU AI Act, and PDPA/GDPR via transparent audit logs, PII masking, and explicit Human-in-the-Loop (HITL) escalation.

---

## 2. Approved System Architecture

We adopt the **Plan-and-Execute Agentic Workflow** (from KIM) over simple RAG, empowered by **Model Context Protocol (MCP)** (from Gemini) and **PostgreSQL statefulness** (from Perplexity).

### 2.1 Logical Flow
```text
Client (React UI) ──[SSE Stream]──> FastAPI API Gateway
                                          │  (Auth, Rate Limit, PII Masking)
                                          ▼
                               LangGraph Orchestrator
                                          │
                            ┌─────────────┴─────────────┐
                            ▼                           ▼
                     1. Planner Node             3. Synthesizer Node
                    (Analyzes query)           (Drafts final response)
                            │                           ▲
                            ▼                           │
                     2. Executor Loop ──────────────────┘
                    (Dispatches to Specialists)

                      [Specialist Agents]
        ┌──────────────┬──────────────┬──────────────┐
  Wealth Advisory  Private Banking   Compliance & Tax   FX & Treasury...
        │              │              │              │
        └──────────────┴──────┬───────┴──────────────┘
                              ▼
                MCP Servers (Secure Tool Execution)
         ├── Banking Ops MCP (Portfolio, Trading APIs)
         ├── Knowledge RAG MCP (Research, Docs via pgvector)
         └── Service Workflow MCP (Onboarding, Appointments)
```

### 2.2 Architectural Decisions & Justifications
*   **APPROVED: Plan-and-Execute Pattern (KIM):** Better than direct RAG. A client asking *"Review my portfolio and check my lending options"* requires distinct steps. Planner routes to *Wealth Advisory*, then *Lending & Credit*, before synthesizing.
*   **APPROVED: Model Context Protocol (MCP):** Enforces strict isolation. The AI brain runs securely, requesting data via HTTP MCP endpoints that have internal RBAC applied.
*   **APPROVED: SSE "Thinking" UI (KIM):** LangGraph execution can take 3-10 seconds. Streaming intermediary steps (`planning` -> `agent_step` -> `synthesizing`) via Server-Sent Events (SSE) ensures a premium user experience.
*   **REJECTED: ChromaDB (KIM):** Replaced with **pgvector** (from Perplexity). Consolidating LangGraph state (Checkpointer), User Sessions, and Vector Embeddings into a single highly-available PostgreSQL cluster reduces infrastructure sprawl and aligns with enterprise banking IT standards.

---

## 3. Technology Stack

| Layer | Technology | Justification |
| :--- | :--- | :--- |
| **LLM Engine** | **Google Gemini 2.0 Flash/Pro** | High performance, native structured output support, massive context window for large financial documents. |
| **Agent Framework** | **LangGraph + PydanticAI** | LangGraph provides stateful "time-travel" graphs; PydanticAI guarantees type-safe inputs/outputs for the MAS FEAT framework. |
| **Backend & API** | **FastAPI (Python 3.12)** | Asynchronous handling of SSE streams and MCP calls. |
| **Database & RAG** | **PostgreSQL (pgvector + JSONB)** | Unified DB for RAG vector search, chat session history, and LangGraph state checkpointing. |
| **Data Integration** | **MCP (Model Context Protocol)** | Standardizes how agents fetch proprietary banking data securely. |
| **Frontend** | **React 19 (TypeScript, Vite, Radix UI)** | Secure, scalable frontend. Auto-generated API client via `@hey-api/openapi-ts` to prevent UI/API drift. |
| **Observability** | **LangSmith + structlog** | Full token tracing, execution graphs, and structured compliance audit logging. |

---

## 4. Core Features Specification

### 4.1 Client-Facing Features (The Concierge)
*   **Natural Language Portfolio Interrogation:** Queries like *"What is my current cash-to-asset ratio?"* mapped securely to the Banking Ops MCP.
*   **Localized "House View" RAG:** Answers macro queries (*"What's the view on Asian high-yield bonds?"*) citing internal CIO reports.
*   **Contextual Market Impact (Informational):** Explains how macroeconomic events map to the user's portfolio without offering rebalancing advice.
*   **SOW & KYC Pre-Validation:** Conversational document checklist tracking for Source of Wealth, reducing friction during onboarding.
*   **Alternatives Matchmaker:** Surfaces eligibility for Hedge Funds or Private Credit based on the client's current tier, prompting an RM meeting.

### 4.2 RM-Facing Features (The Co-Pilot)
*   **Pre-Call Brief Generator:** Compiles recent performance, risk flags, missing documents, and open issues into a 1-page summary before client meetings.
*   **Post-Call Summarization:** Drafts CRM notes from call transcripts, highlighting commitments and compliance flags.
*   **Early Warning Alerts:** Agent monitors portfolios asynchronously for concentration risks or massive drawdowns, alerting the RM via an internal dashboard.

---

## 5. Security, Compliance & Guardrails (MAS & EU AI Act)

### 5.1 Strict Escalation Matrix
The system utilizes a hardcoded RegEx and Semantic router to intercept queries that cross from **information** to **advisory**. If triggered, the LangGraph `Synthesizer` is bypassed directly to the `Escalation` node.

| Query Type | Handled By | Action |
| :--- | :--- | :--- |
| Market outlook / House View | Chatbot | Returns RAG summaries citing dates/sources. |
| Portfolio performance check | Chatbot | Returns raw retrieved data via MCP. |
| *"What should I invest in?"* | **RM Only** | Halts generation. Creates priority CRM ticket. |
| Trust / Legal / Tax structure | **RM Only** | Halts generation. Offers to schedule wealth planner. |
| High distress / Complaints | **RM Only** | Halts generation. Flags compliance dashboard. |

### 5.2 Zero-Trust Security Pipeline
1.  **JWT Auth:** `client_id` is *always* extracted from the validated JWT token by FastAPI, never passed as a user parameter.
2.  **Input Guard:** Middleware strips/masks NRIC, Account Numbers (`\b\d{8,20}\b`), and blocks prompt injection (`"ignore previous instructions"`).
3.  **Scoped RAG:** PostgreSQL vector queries are hard-filtered by `WHERE client_id = current_user` or `is_public = true`. Cross-client data leakage is fundamentally impossible at the SQL layer.

---

## 6. Implementation Folder Structure (Approved)

```text
ubs-chatbot/
├── apps/
│   ├── api/                      # FastAPI Backend
│   │   ├── auth/                 # JWT & LDAP integration
│   │   ├── chat/                 # SSE Streaming routes
│   │   ├── workflow/             # LangGraph Brain
│   │   │   ├── agents/           # Specialist definitions
│   │   │   ├── planner.py        # Routing logic
│   │   │   ├── executor.py       # Tool execution loop
│   │   │   └── graph.py          # StateGraph compilation
│   │   └── security/             # Input guards, PII mask, Audit logger
│   └── ui/                       # React 19 Frontend
│       ├── src/components/       # Chat Window, Thinking Indicator (SSE parsing)
│       └── src/api/generated/    # Auto-typed OpenAPI client
├── mcp_servers/                  # Secure Tool Execution (The Hands)
│   ├── banking_ops/              # Connects to Portfolio APIs
│   ├── knowledge_rag/            # LlamaIndex + pgvector integration
│   └── service_workflow/         # CRM / Appointment APIs
├── docs/                         # Seed data for House Views, FAQs
├── docker-compose.yml            # Local dev (Postgres, Redis, API, UI, MCPs)
└── pyproject.toml                # uv dependencies (LangGraph, FastAPI, etc.)
```

---
*Architect's Note: This document fuses the rigorous compliance and risk definitions of Perplexity with the advanced, scalable Agentic Orchestration and UI capabilities defined by KIM, all while maintaining the core secure "Hands and Brain" execution model defined by Gemini POV.*