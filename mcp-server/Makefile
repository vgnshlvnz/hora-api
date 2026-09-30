.PHONY: install lint fmt type test check run

install:
	uv sync

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

check: lint type test

# Serves http://127.0.0.1:8765/mcp; needs hora-api running at HORA_API_URL.
run:
	uv run hora-mcp
