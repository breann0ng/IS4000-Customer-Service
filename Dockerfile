FROM python:3.12-slim AS backend

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    uv sync --frozen --no-dev --no-editable --no-install-project

COPY apps/ apps/
COPY rag/ rag/
COPY mocks/ mocks/
COPY .env* ./

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]


FROM node:22-alpine AS frontend-build

RUN corepack enable pnpm

WORKDIR /app

COPY apps/ui/package.json apps/ui/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY apps/ui/ .
RUN pnpm run build


FROM nginx:alpine AS frontend

COPY --from=frontend-build /app/dist /usr/share/nginx/html
COPY apps/ui/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
