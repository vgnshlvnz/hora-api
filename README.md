# hora-api

A Python HTTP API that answers "which horas and time windows are favourable for a given person,
date and place". It computes a panchangam-style day (sunrise, sunset, nakshatra, rasi, tithi
transitions), divides it into horas, removes inauspicious windows, and scores what's left against
a person's natal data.

See `CLAUDE.md` for the domain rules and git workflow, and `ROADMAP.md` for progress.

## Make targets

| Target         | What it does                                              |
| -------------- | --------------------------------------------------------- |
| `make install` | Install dependencies with `uv sync`                       |
| `make hooks`   | Enable `.githooks` and the commit template (once per clone) |
| `make lint`    | `ruff check` and `ruff format --check`                    |
| `make fmt`     | Apply `ruff format` and `ruff check --fix`                |
| `make type`    | `mypy --strict`                                           |
| `make test`    | `pytest`                                                  |
| `make cov`     | `pytest` with coverage report                             |
| `make check`   | `lint` + `type` + `test`                                  |
| `make run`     | Serve the API with uvicorn (available once `http-api` lands) |
