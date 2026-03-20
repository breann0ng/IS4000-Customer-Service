Here is a structured review of both files cross-referenced against everything built up in this conversation. The gaps are grouped by severity.

***

## 🔴 Critical Issues (Fix Before Building Further)

### 1. Embedding Dimension Mismatch — Silent Data Corruption Risk
`README.md` lists `sentence-transformers (local)` for embeddings  but `final_chatbot.md` specifies pgvector with a `GEMINI_API_KEY` for the LLM layer. The problem: sentence-transformer models output **384 or 768 dimensions** depending on which model you choose (e.g., `all-MiniLM-L6-v2` = 384 dims), while Gemini's embedding API outputs **768 dims**, and OpenAI's is **1536 dims**. If `rag/ingest.py` uses a different embedding model than `rag/server.py` uses for query embedding, every similarity search will silently return wrong results — the database won't error, it will just give you garbage retrievals. Neither file documents the exact model name and dimension, nor enforces a consistency check at startup. **Fix:** Pick one embedding model explicitly, hardcode its dimension in `config.py`, and add a startup validation that queries pgvector's stored dimension and asserts it matches. [github](https://github.com/langchain-ai/langchain/discussions/21296)

### 2. LDAP Authentication Is Still a Mock
`README.md` explicitly states `auth/` contains **LDAP authentication (mock)**. For a UBS/private banking system this is a showstopper — it means any authentication check in the current codebase is not real. There is no note, TODO, or issue tracker reference about when real LDAP/SSO integration will happen. **Fix:** Either document the production auth plan (Azure AD, LDAP, or SSO via OAuth2) with a clear timeline, or at minimum add a `TODO(SECURITY): Replace with production LDAP/Azure AD integration before pilot` comment in every auth file so this cannot be accidentally shipped. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/113904244/27d36d97-9b68-4e52-b732-9b67227d8c36/README.md)

### 3. Redis Has No Documented Persistence or Isolation Config
`README.md` lists Redis for `mem0` short-context memory  but neither file specifies Redis persistence mode (`RDB` vs `AOF`), TTL policies for session data, or per-client memory isolation strategy. Without `AOF` persistence, a Redis restart wipes all session context silently. Without explicit TTL policies, private banking conversation fragments accumulate in Redis indefinitely — which is a PDPA/GDPR violation (data minimisation principle). **Fix:** Add Redis config to `docker-compose.yml` with `appendonly yes`, set per-client key TTLs (e.g., 24h for session memory), and document the isolation pattern (all keys namespaced as `mem:{client_id}:*`). [mem0](https://mem0.ai/blog/ai-memory-security-best-practices)

***

## 🟠 High Priority Gaps (Fix Before Pilot)

### 4. No GDPR/PDPA Right-to-Erasure Implementation for mem0
Both files use `mem0 + Redis` for agent memory, but neither file mentions a mechanism to honour **GDPR Article 17 Right to Erasure** or Singapore's PDPA equivalent for the memory layer. mem0 stores client preferences, past interactions, and behavioural patterns — all of which qualify as personal data under both regimes. A client asking for their data to be deleted requires you to erase not just their database records but also their mem0 memories and Redis session keys. `mem0` does support `memory.delete_all(user_id=client_id)`, but this endpoint is never wired into a `/data/erasure` API route in either file. **Fix:** Add a `DELETE /api/v1/client/data` endpoint that: (1) deletes all mem0 memories by user_id, (2) flushes Redis keys matching `mem:{client_id}:*`, (3) logs the erasure event in the audit trail. [docs.mem0](https://docs.mem0.ai/core-concepts/memory-operations/delete)

### 5. No LangGraph Fallback / Circuit Breaker for MCP Servers
`final_chatbot.md` shows 4 MCP servers (`banking_ops_server`, `knowledge_server`, `service_workflow_server`, `rag_server`) running as separate processes, but neither file describes what happens when an MCP server is unavailable. In a live banking chatbot, if `banking_ops_server` (port 9001) goes down mid-conversation, the Wealth Advisory agent will hang or throw an unhandled exception, breaking the entire LangGraph execution for that client. There is no retry logic, no circuit-breaker pattern, and no graceful degradation path. **Fix:** Implement `tenacity` retry decorators on all MCP HTTP calls, add a `fallback_response` for each agent that tells the client "portfolio data is temporarily unavailable, please retry or contact your RM," and add a health-check dependency in the graph that skips unavailable agents rather than failing the entire run. [linkedin](https://www.linkedin.com/posts/md-emon-hasan-695483237_agenticai-langgraph-multiagentsystems-activity-7371952766333853697-e7LG)

### 6. Single LLM with No Model-Level Fallback
Both files commit entirely to `gemini-3.1-pro-preview`  with no fallback if the Gemini API is unavailable or returns a rate-limit error (HTTP 429). For a private banking chatbot serving HNWIs who "expect immediate responsiveness", a Google API outage means 100% chatbot downtime with no fallback path. LangGraph with MCP natively supports multi-model fallback chains. **Fix:** Configure a fallback chain in `graph.py`: [mcp-server-langgraph.mintlify](https://mcp-server-langgraph.mintlify.app/guides/agent-architecture)
```python
primary_model="google/gemini-3.1-pro-preview"
fallback_models=["anthropic/claude-opus-4-6", "openai/gpt-4o"]
```

### 7. No Test Directory or Test Suite
`final_chatbot.md`'s folder structure  contains no `tests/` directory at all. `README.md` defines `poe check` for formatting/linting but no test command. This means there is currently zero automated test coverage — no unit tests for node logic, no retrieval accuracy checks, no escalation trigger tests, and no adversarial prompt tests. For a regulated financial system, regulators can ask for evidence of testing. **Fix:** Add a `tests/` folder with at minimum: `test_escalation.py` (the 7 escalation triggers), `test_security.py` (adversarial prompt blocklist), `test_rag.py` (retrieval returns relevant results for 10 reference queries), and `test_agents.py` (each specialist agent returns a valid Pydantic-typed response). [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/113904244/16d61efa-091e-440b-b840-16b4f3ec9d68/final_chatbot.md)

***

## 🟡 Medium Priority Gaps (Fix Before Full Rollout)

### 8. Compliance & Tax Agent Has No Disclaimer Enforcement
The **Compliance & Tax specialist** in `README.md` handles "CRS/FATCA reporting, cross-border tax, regulatory updates"  — which is some of the most legally sensitive territory in the system. Yet neither file specifies that this agent's Synthesizer output must include a mandatory disclaimer ("This is general information only. For personalised tax or legal advice, consult a qualified professional."). The generic system prompt in `final_chatbot.md`  governs all agents equally but tax/legal content requires an additional hard-coded suffix. **Fix:** In the Compliance & Tax agent definition, inject an additional `SystemMessage` that appends the tax/legal disclaimer unconditionally, separate from and in addition to the global system prompt. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/113904244/27d36d97-9b68-4e52-b732-9b67227d8c36/README.md)

### 9. Escalation is Hard-coded RegEx — No Confidence Scoring
`final_chatbot.md` uses a "hardcoded RegEx matrix" to detect advisory intent. This is brittle: phrases like "how exposed am I to rate risk?" or "should I be worried about my EM holdings?" carry clear advisory intent but won't match the exact regex patterns. The EU AI Act and MAS also expect that high-risk AI systems have documented, auditable decision logic for high-stakes actions (like escalation). **Fix:** Supplement RegEx with a lightweight **intent classification step** — a single LLM call with a binary output (`{"escalate": true/false, "reason": "..."}`) using `gemini-3.1-flash` (cheap/fast) before the Planner runs. RegEx remains as the first-pass hard block; LLM classification handles ambiguous cases. [legalnodes](https://www.legalnodes.com/article/eu-ai-act-2026-updates-compliance-requirements-and-business-risks)

### 10. No AI Disclosure at Session Start
Both files describe a secure, authenticated chatbot but neither specifies that clients are told they are interacting with an AI at the start of every session. This is a direct obligation under the EU AI Act (Article 52) and MAS guidelines, and it was documented in `perplexity_pov.md`  as mandatory. Neither the React UI components (`ChatWindow`, `MessageBubble`)  nor the system prompt in `final_chatbot.md`  explicitly enforces this. **Fix:** On session initialisation, before any user message, inject a fixed first assistant message: *"I'm an AI assistant for [Bank Name] Private Banking. For personalised financial advice, please speak with your Relationship Manager."* This should be rendered as a non-deletable system banner in the `ChatWindow` component. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/113904244/16d61efa-091e-440b-b840-16b4f3ec9d68/final_chatbot.md)

### 11. No KPI Targets or Monitoring Definition
`final_chatbot.md` mentions LangSmith + structlog for observability  but defines no KPI targets, no monitoring thresholds, and no quality assurance process. The proposal in `file:99` set clear targets: ≥95% retrieval accuracy, 60–70% resolution rate, <3s response time, CSAT ≥4.2. Without codifying these in the README or a dedicated `docs/monitoring.md`, there is no definition of "the system is working correctly." **Fix:** Add a `## Monitoring & KPIs` section to `README.md` and a `docs/monitoring.md` file that lists the 8 KPI targets, what LangSmith dashboards to create, and what alert thresholds to set. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/113904244/a800d0e8-27c4-481a-a5fc-99c1fe680452/Private-Banking-Chatbot-Proposal.pdf)

### 12. No Document Freshness / Re-ingestion Strategy
`README.md` describes `poe rag-ingestion` as a one-time setup command. But the most valuable RAG content — CIO reports, investment outlooks, house view updates — changes weekly or monthly. Neither file defines: how often documents are re-ingested, whether old chunks are deleted before re-ingestion (avoiding stale data), or who is responsible for uploading new documents to `docs/`. A client asking "what is the bank's current view on US equities?" could get an answer citing a 6-month-old outlook if re-ingestion is never run. **Fix:** Add a `poe rag-refresh` task that: (1) deletes existing embeddings for documents whose source file has changed (hash-check), (2) re-ingests only changed/new documents, and (3) logs ingestion timestamp per document in a metadata table for auditability. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/113904244/27d36d97-9b68-4e52-b732-9b67227d8c36/README.md)

***

## 🔵 Lower Priority Gaps (Quality Improvements)

### 13. Missing Client-Facing Unique Features from the Full Spec
Compared to the full feature spec built in this conversation, both files are missing several differentiating client features that were prioritised : the **Goal-Oriented Portfolio View** (accumulation vs preservation buckets), the **Trophy Asset & Financing Explainer**, the **Pre-Call Brief generator for clients** (only the RM version exists ), and the **Alternatives Concierge** for hedge fund/private credit education. These are medium-term but should be in the `## Future Work` section of the README to prevent them being forgotten, yet `README.md`'s Future Work section  does not mention any of them. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/113904244/16d61efa-091e-440b-b840-16b4f3ec9d68/final_chatbot.md)

### 14. No Multilingual Support Plan
The proposal  specifically mentioned multilingual support (English, Mandarin, Cantonese, Arabic, French) for global HNWI clientele. Gemini 3.1 Pro natively supports these languages but neither file specifies language detection, language-scoped system prompts, or multilingual RAG (whether the knowledge base is indexed in multiple languages). This is a `Future Work` item that should at least be documented as a known gap. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/113904244/a800d0e8-27c4-481a-a5fc-99c1fe680452/Private-Banking-Chatbot-Proposal.pdf)

### 15. No OpenAPI Drift Check in CI
`README.md` lists `scripts/check_openapi_drift.py` as a CI check, which is excellent. However, neither file shows this integrated into a CI pipeline (`GitHub Actions`, `pre-commit`, or similar). The `poe check` task covers formatting/linting but `check_openapi_drift.py` appears to be a standalone script that developers must remember to run manually. **Fix:** Add `check_openapi_drift` to the `poe check` task chain so it runs automatically on every commit. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/113904244/27d36d97-9b68-4e52-b732-9b67227d8c36/README.md)

### 16. `docs/` Folder Has No Version or Freshness Metadata
Both files show a `docs/` folder as the seed data source for RAG  but neither defines a naming convention or metadata schema for documents (e.g., `cio_report_2026_Q1.pdf`, with `source`, `published_date`, `category` fields). Without this, when a client asks "what is the latest house view?", the bot cannot determine which chunk is newest. **Fix:** Enforce a metadata schema in `ingest.py` that extracts or accepts `{"source": "...", "category": "...", "published_date": "..."}` per document, stores it in pgvector's metadata JSONB column, and filters retrieval by `published_date DESC` for time-sensitive queries. [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/113904244/16d61efa-091e-440b-b840-16b4f3ec9d68/final_chatbot.md)

***

## Summary Priority Table

| # | Issue | File Affected | Priority |
|---|---|---|---|
| 1 | Embedding dimension mismatch | `rag/ingest.py`, `rag/server.py`, `config.py` | 🔴 Critical |
| 2 | LDAP auth is a mock | `apps/api/auth/` | 🔴 Critical |
| 3 | Redis has no persistence / TTL / isolation | `docker-compose.yml`, `memory/` | 🔴 Critical |
| 4 | No Right-to-Erasure for mem0/Redis | `apps/api/` | 🟠 High |
| 5 | No fallback / circuit breaker for MCP servers | `workflow/executor.py` | 🟠 High |
| 6 | Single LLM, no model fallback | `workflow/graph.py` | 🟠 High |
| 7 | No test suite at all | Missing `tests/` dir | 🟠 High |
| 8 | Compliance & Tax agent missing hard disclaimer | `workflow/agents/` | 🟡 Medium |
| 9 | Escalation is RegEx-only, no confidence scoring | `workflow/planner.py` | 🟡 Medium |
| 10 | No AI disclosure at session start | `ui/`, system prompt | 🟡 Medium |
| 11 | No KPI targets or monitoring definition | `README.md` | 🟡 Medium |
| 12 | No document re-ingestion/freshness strategy | `rag/ingest.py` | 🟡 Medium |
| 13 | Missing client-facing differentiating features | `README.md` Future Work | 🔵 Low |
| 14 | No multilingual support plan | `README.md` Future Work | 🔵 Low |
| 15 | OpenAPI drift check not in CI pipeline | `pyproject.toml` | 🔵 Low |
| 16 | No document metadata schema for RAG freshness | `rag/ingest.py` | 🔵 Low |