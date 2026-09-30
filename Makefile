.PHONY: install hooks lint fmt type test cov check mcp-check run

install:
	uv sync

hooks:
	git config core.hooksPath .githooks
	git config commit.template .gitmessage

lint:
	uv run ruff check .
	uv run ruff format --check .

fmt:
	uv run ruff format .
	uv run ruff check --fix .

type:
	uv run mypy

test:
	uv run pytest

cov:
	uv run pytest --cov=hora_api --cov-report=term-missing

check: lint type test mcp-check

# The MCP server is a separate uv project in mcp-server/ with its own environment and gate.
mcp-check:
	$(MAKE) -C mcp-server install
	$(MAKE) -C mcp-server check

# Needs hora_api.api.app, which arrives with the http-api feature.
run:
	uv run uvicorn hora_api.api.app:app --reload
