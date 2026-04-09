# Repository Guidelines

## Project Structure & Module Organization
`apps/api/` contains the FastAPI backend: `auth/`, `chat/`, `database/`, `memory/`, `security/`, and the LangGraph workflow in `workflow/`. `apps/ui/` contains the Vite + React frontend; reusable UI lives in `src/components/`, route pages in `src/pages/`, hooks in `src/hooks/`, and generated API code in `src/api/generated/`. RAG ingestion and retrieval live in `rag/`. Mock MCP services are in `mcp_servers/`, helper scripts in `scripts/`, and backend tests belong in `tests/`.

## Build, Test, and Development Commands
Install with `uv sync` and `cd apps/ui && pnpm install`.

- `poe dev-api`: run FastAPI with reload on `:8000`.
- `poe dev-ui`: run the Vite frontend on `:5173`.
- `poe mock-mcp`: start all local MCP and RAG servers on ports `9001-9004`.
- `poe rag-ingestion`: ingest documents from `docs/` into Postgres/pgvector.
- `poe generate-api-client`: export OpenAPI and regenerate `apps/ui/src/api/generated/`.
- `poe check`: run Ruff format/check, Python type checks, and OpenAPI drift validation.
- `cd apps/ui && pnpm run build`: production UI build.
- `poe docker-up`: build and run the full stack with Docker Compose.

## Coding Style & Naming Conventions
Python targets 3.12+ with Ruff enforcing a 100-character line length, double quotes, import sorting, and Google-style docstrings. Use 4-space indentation and snake_case for Python modules, functions, and variables. React/TypeScript files use 2-space indentation, PascalCase filenames such as `ChatPage.tsx`, and camelCase for hooks and helpers such as `useAuth.ts`. Treat `src/api/generated/` as generated output.

## Testing Guidelines
There is not yet a broad automated test suite, so `poe check` is the minimum gate before opening a PR. Add backend tests under `tests/` using `test_*.py` naming. For workflow, auth, or API changes, include focused request/response coverage and rerun OpenAPI drift checks through `poe check`. For frontend changes, verify `pnpm run build` and document manual test steps in the PR.

## Commit & Pull Request Guidelines
Recent history mixes imperative commits (`added account performance page`) with scoped docs commits (`docs: exclude ...`). Prefer concise imperative subjects, optionally scoped, such as `feat: add lending agent fallback` or `docs: update setup steps`. Keep commits focused. PRs should include a summary, linked issue or task, screenshots for UI changes, and a note on validation performed (`poe check`, `pnpm run build`, manual chat flow, etc.).

## Security & Configuration Tips
Copy `.env.example` to `.env` and keep secrets out of git. Set `GEMINI_API_KEY`, database, Redis, and MCP URLs locally. Do not commit real customer data; use the mock records in `mocks/customer_data/`.
