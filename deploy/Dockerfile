# syntax=docker/dockerfile:1
# Build from the repository root:  docker build -f deploy/Dockerfile --target api .
# Targets: api (the HTTP API) and mcp (the MCP server).

FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
COPY --from=ghcr.io/astral-sh/uv:0.8.17 /uv /bin/uv
RUN useradd --system --uid 10001 --home-dir /app --shell /usr/sbin/nologin hora
WORKDIR /app
COPY deploy/healthcheck.py /app/healthcheck.py

FROM base AS api
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY data ./data
RUN uv sync --frozen --no-dev
ENV PATH="/app/.venv/bin:$PATH" \
    DATA_DIR=/app/data \
    PROFILES_PATH=/profiles/profiles.yaml
USER hora
EXPOSE 8000
CMD ["uvicorn", "hora_api.api.app:app", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS mcp
COPY mcp-server/pyproject.toml mcp-server/uv.lock mcp-server/README.md ./
COPY mcp-server/src ./src
RUN uv sync --frozen --no-dev
ENV PATH="/app/.venv/bin:$PATH" \
    HORA_MCP_HOST=0.0.0.0
USER hora
EXPOSE 8765
CMD ["hora-mcp"]
