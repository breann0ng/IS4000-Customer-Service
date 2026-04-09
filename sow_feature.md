# Source of Wealth (SOW) Feature Specification

## Purpose

This document compiles the recommended product, architecture, agent design, MCP/RAG integration, implementation plan, and acceptance criteria for a Source of Wealth (SOW) checking feature in the pre-onboarding flow.

The core design principle is:

> AI handles structure, extraction, validation support, and workflow orchestration.
> Humans handle judgment, accountability, risk acceptance, and final approval.

This feature should be implemented as a case-management and compliance-support capability first, and a chatbot experience second.

---

## Goals

- Reduce RM and compliance back-and-forth during pre-onboarding
- Force clients into structured SOW disclosures instead of free-text narratives
- Collect and classify supporting documents
- Cross-check declarations against evidence and external registries
- Generate clear missing-document lists and discrepancy flags
- Preserve full auditability and human decision ownership

## Non-goals

- Fully autonomous SOW approval
- LLM-only verification of wealth legitimacy
- Replacing compliance reviewers
- Using chat transcripts as the system of record for compliance

---

## Current Repo Fit

The current architecture already has the right high-level pattern:

- LangGraph orchestration in `apps/api/workflow/`
- Specialist agents in `apps/api/workflow/agents/`
- MCP-backed tool execution through `apps/api/workflow/tools/mcp_client.py`
- RAG retrieval through `apps/api/workflow/tools/rag_tool.py`
- Mock MCP servers in `mcp_servers/`
- JWT, RBAC, and audit hooks already present in the MCP layer

Relevant current constraints:

- Planner and synthesizer already support model tiering through explicit config.
- MCP-backed specialist handlers currently use a shared `settings.gemini_model`, which means true per-agent model assignment is not yet implemented inside the MCP layer.
- Existing database models currently only cover users, chat sessions, chat messages, and RAG documents. There is no onboarding or compliance case model yet.

---

## 1. Should We Reuse Existing Agents or Create Separate SOW Agents?

## Short answer

Use a hybrid approach:

- Reuse existing agents for conversational guidance and policy explanation.
- Create separate SOW-specific agents and deterministic services for case handling, document intelligence, corroboration, and review support.

## Recommendation

### Reuse existing agents for:

- `client_services`
  - Client-facing intake guidance
  - Missing-document reminders
  - Case status updates
  - Explaining next steps

- `compliance_tax`
  - Explaining SOW policy requirements
  - Clarifying why documents are needed
  - Helping staff interpret procedural requirements

### Do not rely on existing agents alone for:

- Case creation and state transitions
- SOW declaration persistence
- Document classification and extraction pipeline
- Cross-document corroboration
- Registry lookups
- Final reviewer workbench logic
- Audit-grade decision logging

### Create separate SOW-specific components for:

- SOW case orchestration
- Document intelligence
- Corroboration and discrepancy analysis
- External verification
- RM/compliance copilots
- Deterministic rule engine

## Why separate SOW agents are needed

The existing agents are broad domain specialists. SOW screening needs:

- tightly scoped inputs and outputs
- repeatable evidence mapping
- rule-based risk flags
- auditable state transitions
- role-based write and execute actions
- a clear distinction between client-visible and reviewer-only outputs

That makes SOW a poor fit as "just another prompt" inside `client_services` or `compliance_tax`.

## Final recommendation

- Keep `client_services` and `compliance_tax` as supporting agents.
- Build a dedicated SOW onboarding module and a dedicated SOW MCP surface.
- Treat the deterministic rules engine as the primary decision-support layer.
- Treat LLM agents as helpers around that core.

---

## 2. Proposed Agent Architecture for SOW

## Design principle

Not every SOW component should be an LLM agent. The best design mixes:

- LLM agents for intake, summarization, extraction assistance, and reviewer support
- deterministic services for validation, scoring, status transitions, and final decision support
- MCP tools for controlled access to internal systems and external data

## Proposed architecture

### A. SOW Intake Orchestrator Agent

Purpose:

- Drive the client through structured pre-onboarding questions
- Convert free-form answers into a normalized SOW profile
- Dynamically branch based on declared wealth source

Inputs:

- client answers
- onboarding case state
- SOW evidence matrix
- allowed question schema

Outputs:

- normalized SOW declaration
- missing field list
- required document checklist

Should it decide approval?

- No

### B. SOW Document Intelligence Agent

Purpose:

- Classify uploaded documents
- Extract key structured fields
- Link documents to claims

Inputs:

- uploaded file metadata
- OCR output
- expected document types

Outputs:

- document type suggestion
- extracted entities and values
- confidence score
- unmatched-document flags

Should it decide approval?

- No

### C. SOW Corroboration Agent

Purpose:

- Compare declared SOW against extracted data and external evidence
- Build claim-to-evidence mapping
- Generate inconsistency explanations for reviewers

Inputs:

- SOW declarations
- extracted document fields
- external verification results

Outputs:

- discrepancy list
- evidence coverage map
- reviewer summary
- recommended escalation reason

Should it decide approval?

- No. It may recommend, but the deterministic rule engine and reviewers own decisions.

### D. SOW External Verification Agent

Purpose:

- Orchestrate registry and screening lookups
- Normalize external data into the case model

Inputs:

- company names
- registration numbers
- jurisdictions
- person/entity identifiers

Outputs:

- registry matches
- directorship/shareholding confirmations
- sanctions/adverse-media summaries

Should it decide approval?

- No

### E. SOW Case Manager Agent

Purpose:

- Keep the case moving
- Track status, pending tasks, reviewer handoffs, and client notifications

Inputs:

- case state
- checklist state
- reviewer decisions

Outputs:

- next-best action
- reminders
- status messages

Should it decide approval?

- No

### F. RM Copilot Agent

Purpose:

- Summarize SOW profile for RMs
- Draft outreach and missing-document requests
- Prepare a case summary before handoff to compliance

Inputs:

- case data
- client narrative
- discrepancy and checklist outputs

Outputs:

- RM summary
- client communication drafts
- suggested follow-up questions

Should it decide approval?

- No

### G. Compliance Review Assistant Agent

Purpose:

- Help compliance reviewers interpret the evidence set
- Draft exception memos and reviewer notes
- Explain why the case was flagged

Inputs:

- full case data
- rules-engine outputs
- policy documents
- review history

Outputs:

- review summary
- exception memo draft
- rationale draft for approve / reject / request-more-info

Should it decide approval?

- No. Human reviewer approves.

### H. SOW Rules Engine

Purpose:

- Deterministically assess completeness, contradictions, thresholds, and escalation triggers

Inputs:

- declared profile
- required documents
- extracted structured values
- external verification results

Outputs:

- missing docs
- hard-stop flags
- risk flags
- recommended status

Should it decide approval?

- It may produce `recommended_status`, but final approval must still be recorded by a human unless explicitly approved by policy for low-risk auto-pass.

## Recommended end-to-end flow

1. Create SOW case
2. Intake agent collects structured declarations
3. Case manager computes required evidence list
4. Client uploads documents
5. Document intelligence classifies and extracts
6. External verification fetches company/entity corroboration
7. Rules engine evaluates completeness and contradictions
8. Corroboration agent drafts reviewer summary
9. RM copilot prepares RM-facing summary and client follow-up
10. Compliance review assistant prepares reviewer memo
11. Human reviewer records final decision
12. Case manager notifies client and RM

---

## 3. Recommended Tiered Agent Assignment

## Important implementation note

Today, planner and synthesizer already support explicit model tiering. However, the MCP-backed specialist handlers currently share a single `settings.gemini_model`. To implement the table below properly, add per-agent or per-tool model configuration for MCP handlers.

Suggested config additions:

- `wealth_advisory_model`
- `compliance_tax_model`
- `client_services_model`
- `private_banking_model`
- `lending_credit_model`
- `fx_treasury_model`
- `sow_intake_model`
- `sow_document_intelligence_model`
- `sow_corroboration_model`
- `sow_external_verification_model`
- `sow_rm_copilot_model`
- `sow_compliance_review_model`

## Recommended table

| Agent | Model | Reason |
| --- | --- | --- |
| Wealth Advisory | Gemini 2.5 Pro | Complex multi-source reasoning across RAG, market context, and portfolio analysis |
| Compliance & Tax | Gemini 2.5 Pro | Deep regulatory reasoning, policy synthesis, and nuanced escalation support |
| Client Services | Gemini 2.5 Flash | Intake guidance, checklist explanation, status updates, and light formatting |
| Private Banking | Gemini 2.5 Flash | Structured data retrieval and light presentation logic |
| Lending & Credit | Gemini 2.5 Flash | Structured retrieval and moderate explanatory formatting |
| FX & Treasury | Gemini 2.5 Flash | Rate lookup, lightweight synthesis, and formatted response generation |
| SOW Intake Orchestrator | Gemini 2.5 Flash | Conversational branching, structured capture, and checklist generation |
| SOW Document Intelligence | Gemini 2.5 Flash | Document classification, extraction, normalization, and confidence tagging |
| SOW Corroboration | Gemini 2.5 Pro | Multi-document reasoning, claim-evidence mapping, and discrepancy explanation |
| SOW External Verification | Gemini 2.5 Flash | Mostly connector orchestration and normalization with limited deep reasoning |
| SOW Case Manager | Gemini 2.5 Flash | Status orchestration, next-step generation, and workflow messaging |
| RM Copilot | Gemini 2.5 Flash | Draft summaries, outreach templates, and reviewer handoff notes |
| Compliance Review Assistant | Gemini 2.5 Pro | Holistic case interpretation, exception memo drafting, and reviewer rationale support |
| SOW Rules Engine | No LLM | Deterministic rule evaluation for auditability and explainability |

## Why this tiering is recommended

- Flash-tier models are sufficient for structured capture, extraction, routing, status messaging, and summarization.
- Pro-tier models should be reserved for tasks involving conflicting evidence, holistic reasoning, and reviewer-facing synthesis.
- Deterministic rules should own threshold-based decisions and hard-stop logic.

---

## 4. Do We Need MCP Server Integration?

## Recommendation

Yes. For this codebase, MCP integration is strongly recommended.

## Why MCP is a good fit here

The current architecture already uses MCP for:

- internal tool invocation
- role-based access control
- audit logging
- transport isolation between orchestrator and specialist services
- extensible tool registration

SOW is exactly the kind of feature that benefits from MCP because it involves:

- read/write case actions
- reviewer-only actions
- possible human confirmation for final decisions
- external system connectors
- auditable access boundaries

## What to reuse

- Reuse the existing MCP client and JWT/RBAC pattern
- Reuse existing `READ`, `WRITE`, and `EXECUTE` tool tiers
- Reuse the existing audit trail structure in the MCP servers

## What to add

Create a dedicated MCP server, for example:

- `mcp_servers/onboarding_server.py`

This is better than overloading the current service workflow server because SOW introduces:

- compliance-sensitive write operations
- reviewer-only actions
- case lifecycle transitions
- document extraction and rule execution
- more granular permissions

## Recommended SOW MCP tools

### READ tools

- `get_sow_case`
- `list_sow_cases`
- `get_sow_required_documents`
- `get_sow_missing_documents`
- `get_sow_discrepancies`
- `get_sow_review_summary`
- `lookup_company_registry`
- `lookup_sanctions_screening`

### WRITE tools

- `create_sow_case`
- `update_sow_profile`
- `save_sow_declaration`
- `attach_sow_document`
- `save_document_extraction`
- `submit_sow_case`
- `request_additional_documents`
- `update_sow_case_status`

### EXECUTE tools

- `run_sow_checks`
- `run_sow_external_verification`
- `record_sow_decision`
- `override_sow_recommendation`

## Recommended RBAC

- `HNW_CLIENT`
  - READ: own case status, requirements, missing docs
  - WRITE: own declarations and document uploads if permitted
  - EXECUTE: none

- `RM` / `EMPLOYEE`
  - READ: assigned cases
  - WRITE: request docs, annotate, submit
  - EXECUTE: limited orchestration actions if approved

- `COMPLIANCE`
  - READ: full case
  - WRITE: review notes, status changes
  - EXECUTE: final decision and overrides

## How MCP should be integrated

1. Add a new onboarding MCP server file
2. Define tool schemas for SOW operations
3. Implement handlers backed by onboarding service methods
4. Apply RBAC by tool tier
5. Require HITL or explicit confirmation for final decision tools
6. Expose the server URL in config
7. Add SOW agent wrappers in `apps/api/workflow/agents/`
8. Dispatch them in the executor or a dedicated onboarding flow

## Recommended implementation boundary

- Use MCP for case actions, verification calls, and reviewer operations.
- Keep deterministic rules in backend services.
- Let agents call MCP tools rather than writing directly to the database.

---

## 5. Do We Need RAG Integration?

## Recommendation

Yes, but with a narrow scope.

Use RAG for:

- SOW policy retrieval
- document requirement guidance
- internal onboarding SOPs
- exception handling playbooks
- reviewer guidance and standard wording

Do not use RAG for:

- storing case evidence
- storing client-uploaded documents as the system of record
- deciding approval outcomes
- acting as the source of truth for extracted client facts

## Why RAG is useful here

SOW flows depend heavily on internal policy and procedural consistency. RAG helps agents:

- explain why documents are needed
- retrieve the correct evidence checklist
- reference escalation criteria
- generate consistent reviewer and RM summaries

## What content should be ingested

- onboarding SOPs
- SOW/Source of Funds policy documents
- evidence matrix by wealth type
- exception-handling guidelines
- reviewer playbooks
- sample approved evidence patterns
- approved client communication templates

## Recommended RAG categories / retrieval profiles

Suggested new categories:

- `onboarding`
- `sow_policy`
- `sow_review`

Suggested new retrieval profiles:

- `sow_intake`
- `sow_case_manager`
- `sow_compliance_review`

## How RAG should be integrated

1. Add SOW policy and SOP documents into the ingestion corpus
2. Tag documents with `category`, `jurisdiction`, `policy_type`, and `audience`
3. Extend retrieval profiles to SOW-specific use cases
4. Pass retrieved policy text into:
   - Intake Orchestrator
   - Client Services
   - Compliance Review Assistant
5. Keep the rules engine independent from retrieved prose

## RAG guardrails

- The rules engine should not depend on similarity search to know what to do.
- RAG should assist explanation, not replace encoded rules.
- Final reviewer decisions must cite stored case data and policy references, not only LLM output.

---

## 6. Proposed Data Model

Add dedicated onboarding/compliance entities. Suggested tables:

- `onboarding_cases`
  - case id, client id, assigned RM, status, risk band, timestamps

- `sow_profiles`
  - overall narrative, occupation, jurisdictions, expected initial funding, expected activity

- `sow_declarations`
  - one row per wealth claim
  - type, amount, currency, date, jurisdiction, notes

- `sow_documents`
  - uploaded file metadata, storage path, OCR status, doc type, review status

- `sow_document_extractions`
  - extracted fields, confidence, normalized values, extractor version

- `sow_evidence_links`
  - maps a declaration to one or more supporting documents or external verification items

- `sow_checks`
  - rules-engine runs, version, recommended status, summary

- `sow_flags`
  - missing-doc, mismatch, adverse-media, high-risk-jurisdiction, manual-review-required

- `sow_decision_logs`
  - reviewer, action, rationale, override reason, timestamps

- `sow_external_verifications`
  - registry/screening results and provenance

## Suggested statuses

- `DRAFT`
- `PENDING_CLIENT_INFO`
- `PENDING_DOCUMENTS`
- `CHECKS_RUNNING`
- `READY_FOR_RM_REVIEW`
- `READY_FOR_COMPLIANCE_REVIEW`
- `APPROVED`
- `REJECTED`
- `ESCALATED`

## Suggested rules-engine outputs

- `PASS`
- `PASS_WITH_CONDITIONS`
- `PENDING_DOCS`
- `REVIEW`
- `REJECT`

---

## 7. Recommended Workflow Design

## System flow

1. RM or client creates SOW case
2. Intake agent collects structured declarations
3. Rules engine computes required evidence checklist
4. Client uploads docs
5. Document intelligence classifies and extracts fields
6. External verification resolves company/entity corroboration
7. Rules engine runs completeness and contradiction checks
8. Corroboration agent creates evidence summary
9. RM copilot drafts RM view and follow-ups
10. Compliance assistant drafts reviewer memo
11. Human reviewer records final decision
12. Case manager updates status and notifications

## Workflow integration with existing LangGraph

Recommended approach:

- Add a dedicated onboarding path instead of forcing the normal chat planner to own the entire SOW lifecycle.
- The planner may route to SOW entry points for:
  - starting onboarding
  - checking case status
  - explaining document requirements
  - summarizing case progress

Recommended graph usage:

- Use current planner/executor flow for conversational interactions.
- Use dedicated onboarding services and MCP tools for case-state transitions.
- Optionally add a pre-planner `sow_check_node` or onboarding intent node for onboarding-specific routes.

---

## 8. Implementation Tasks and Acceptance Criteria

Below is the recommended task breakdown to complete the SOW feature.

### Task 1. Define SOW policy scope and evidence matrix

Deliverables:

- supported SOW types for v1
- required fields per type
- mandatory and optional evidence list
- red flag list
- escalation conditions

Acceptance criteria:

- documented v1 SOW taxonomy exists
- every supported SOW type maps to a required evidence checklist
- compliance stakeholders confirm the matrix is reviewable and usable

### Task 2. Add onboarding database models and migration

Deliverables:

- onboarding/SOW tables
- SQLAlchemy models
- migration files

Acceptance criteria:

- a case can persist declarations, documents, checks, flags, and decisions
- audit logs survive across sessions
- case history can be reconstructed from the database alone

### Task 3. Add onboarding service layer

Deliverables:

- `apps/api/onboarding/service.py`
- case lifecycle methods
- document linking methods
- rules-engine entry points

Acceptance criteria:

- service layer supports create, update, submit, check, review, and decision actions
- business logic is testable without going through chat

### Task 4. Add onboarding API routes

Deliverables:

- `apps/api/onboarding/routes.py`
- request/response schemas
- auth and role checks

Acceptance criteria:

- RM/client can create and update cases through API
- reviewer endpoints are role-gated
- OpenAPI includes the onboarding endpoints

### Task 5. Build the deterministic SOW rules engine

Deliverables:

- required-doc computation
- contradiction checks
- threshold rules
- recommended status output

Acceptance criteria:

- rules engine can detect missing documents
- rules engine can flag material contradictions
- rules engine returns structured outputs with reasons
- rules are versioned or traceable

### Task 6. Build document upload, classification, and extraction pipeline

Deliverables:

- document metadata persistence
- OCR hook or placeholder
- document-type classifier
- extraction schema per doc type

Acceptance criteria:

- uploaded files can be attached to a case
- system can suggest a document type and extracted fields
- unmatched or low-confidence documents are flagged
- reviewer can see extracted values and confidence

### Task 7. Add external verification connector layer

Deliverables:

- connector abstraction for company registry and screening sources
- normalized response schema
- storage for verification provenance

Acceptance criteria:

- declared company ownership can be looked up through a connector
- external responses are stored with timestamps and source metadata
- connector failures do not crash the case flow

### Task 8. Create SOW MCP server and tools

Deliverables:

- `mcp_servers/onboarding_server.py`
- tool schemas
- RBAC mapping
- HITL handling for final decisions

Acceptance criteria:

- SOW tools are discoverable via MCP `tools/list`
- READ/WRITE/EXECUTE permissions behave correctly
- final decision actions require elevated access and confirmation
- MCP calls are audit logged

### Task 9. Add SOW-specific agent wrappers

Deliverables:

- `apps/api/workflow/agents/sow_intake.py`
- `apps/api/workflow/agents/sow_review.py`
- optionally other thin wrappers as needed

Acceptance criteria:

- agents can call SOW MCP tools successfully
- agent outputs are structured enough to support UI and reviewer workflows
- failures degrade gracefully with clear messages

### Task 10. Refactor model configuration for per-agent tiering

Deliverables:

- new config keys for per-agent models
- MCP handlers updated to use tool-specific models

Acceptance criteria:

- SOW Corroboration and Compliance Review can run on Pro-tier models
- lightweight SOW tasks can run on Flash-tier models
- model assignments are environment-configurable

### Task 11. Add SOW documents to RAG corpus

Deliverables:

- onboarding/SOW policies in `docs/`
- ingestion metadata for category and audience
- retrieval profile updates

Acceptance criteria:

- client services and compliance assistants can retrieve SOW policy content
- retrieved policy chunks are relevant to SOW prompts
- no client-uploaded evidence is stored only in RAG

### Task 12. Integrate SOW into workflow routing

Deliverables:

- onboarding intent handling in workflow
- case status retrieval path
- document requirement explanation path

Acceptance criteria:

- user can ask to start onboarding and be routed correctly
- user can ask what documents are missing and get a case-specific answer
- workflow uses SOW tools without bypassing case state

### Task 13. Build RM/compliance workbench UI

Deliverables:

- case list page
- case detail page
- evidence and discrepancy panels
- reviewer action controls

Acceptance criteria:

- RM can see pending cases and missing docs
- compliance can review evidence-by-claim mapping
- reviewer can record approve/reject/request-more-info with rationale

### Task 14. Build client onboarding UI flow

Deliverables:

- intake form / chat-assisted structured flow
- upload experience
- progress tracker
- missing-document view

Acceptance criteria:

- client can complete structured declarations without free-text only
- client can upload documents and see what is still missing
- client sees status changes without exposing internal compliance notes

### Task 15. Add audit logging and reviewer override controls

Deliverables:

- action audit events
- model/extraction provenance
- override rationale capture

Acceptance criteria:

- every case transition is traceable
- every override stores actor, time, and reason
- reviewer can distinguish machine recommendation from human decision

### Task 16. Add tests

Deliverables:

- backend unit tests for rules engine
- API tests for onboarding routes
- workflow tests for routing
- manual QA scripts for end-to-end cases

Acceptance criteria:

- rules engine tests cover supported SOW types and contradiction scenarios
- API tests cover role restrictions and lifecycle transitions
- `poe check` passes
- frontend build passes if UI changes are included

### Task 17. Pilot rollout

Deliverables:

- sample seeded cases
- operational runbook
- reviewer training notes

Acceptance criteria:

- pilot users can complete the flow end to end
- compliance confirms that AI output is assistive, not authoritative
- no production case requires reading raw chat history to determine status

---

## 9. Suggested Phase Plan

### Phase 1. Foundation

Scope:

- case model
- onboarding APIs
- structured intake
- document upload metadata
- manual review status flow

### Phase 2. Intelligence

Scope:

- document classification
- extraction pipeline
- rules engine
- discrepancy generation

### Phase 3. Orchestration

Scope:

- onboarding MCP server
- SOW agents
- workflow routing
- RM/compliance copilots

### Phase 4. Expansion

Scope:

- external registry integrations
- sanctions/adverse media
- multi-jurisdiction support
- advanced structure handling

---

## 10. Recommended Technical Structure

Suggested new backend structure:

```text
apps/api/onboarding/
  __init__.py
  models.py
  schemas.py
  routes.py
  service.py
  rules.py
  document_intelligence.py
  external_verification.py
  audit.py
```

Suggested workflow additions:

```text
apps/api/workflow/agents/
  sow_intake.py
  sow_case_manager.py
  sow_review.py
```

Suggested MCP addition:

```text
mcp_servers/
  onboarding_server.py
```

Suggested documentation additions:

```text
docs/
  sow_policy/
  onboarding_playbooks/
  evidence_matrices/
```

---

## 11. Key Product and Compliance Guardrails

- No autonomous approval for high-risk or ambiguous cases
- No final approval based purely on LLM output
- No bypass of reviewer rationale capture
- No use of RAG as the system of record for case evidence
- No direct client access to internal reviewer notes
- No hidden scoring without reviewer-visible reasons
- No coupling of final approval logic to prompt wording alone

---

## 12. Final Recommendation

For this repo, the best approach is:

1. Build SOW as a dedicated onboarding/compliance feature with its own data model and service layer
2. Reuse existing `client_services` and `compliance_tax` agents only for guidance and explanation
3. Introduce a dedicated SOW MCP server for auditable tool access and reviewer actions
4. Use RAG narrowly for policy/SOP retrieval, not for evidence truth
5. Add SOW-specific agents only where LLM assistance adds value
6. Keep the rules engine deterministic and keep final approval human-owned

This gives you a design that matches the current repo architecture while preserving compliance-grade boundaries.
