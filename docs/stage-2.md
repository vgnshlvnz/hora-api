# Stage 2: consumers and hosting

Version 0.2.0. Builds on the stage 1 query API (`docs/stage-1.md`). Decisions are recorded in
`docs/stage-2-decisions.md`.

## What shipped

| Feature | Tag | What it is |
| ------- | --- | ---------- |
| chat-cards | `s2-chat-cards` | `GET /v1/cards/day` and `GET /v1/cards/rasi`: client-neutral chat cards rendered by the API |
| mcp-server | `s2-mcp-server` | `mcp-server/` (hora-mcp): an MCP server over streamable HTTP wrapping the API |
| self-hosting | `s2-self-hosting` | `deploy/` (Docker Compose, systemd units), `scripts/smoke.sh`, `docs/self-hosting.md` |

Skipped: `esp32-client` (the ESP32 calling the API over the network). It was decided and then
dropped from this stage; revisit later.

## Chat cards

A card has a `kind`, `title`, `subtitle`, ordered `sections` and a `footer`. Each section has a
stable `id`, a `title` and label/value `rows`; each row has a `tone` of `good`, `bad` or
`neutral`. Times are ready-to-show `HH:MM` strings in the request's timezone, with `+1` after
local midnight. The footer and `unverified_tables` name any unverified tables in use.

- Day card sections: `sun`, `moon`, `avoid`, `nalla_neram` (Gowri, its own layer), `horas`.
- Rasi card sections: `chandrashtama`, `best`, `all`.

The reference output for the golden Petaling Jaya day is `docs/golden/2026-09-30-pj-cards.json`
(regenerate by calling both endpoints with the request recorded at the top of the file).
There is no personal-windows card; it was left out of scope.

## MCP server

Tools: `hora_day_card`, `hora_rasi_card`, `hora_personal_horas`. All arguments are optional
except `profile_id` on the personal tool. It listens on `127.0.0.1:8765/mcp` by default. To serve
other machines set `HORA_MCP_HOST`, `HORA_MCP_ALLOWED_HOSTS` and `HORA_MCP_TOKEN`
(`mcp-server/README.md`). It is a separate uv project; the root `make check` runs its checks too.

## Self-hosting

LAN only over plain HTTP, on Docker Compose or systemd, with `API_KEYS` and `HORA_MCP_TOKEN`
mandatory. See `docs/self-hosting.md` for install, profiles backup and restore, upgrade and
rollback, and troubleshooting, and run `scripts/smoke.sh` after a deployment.

## Run it

```
make install && make hooks
make check                      # API and MCP server: ruff, mypy, pytest
make run                        # API on http://127.0.0.1:8000
make -C mcp-server run          # MCP server on http://127.0.0.1:8765/mcp
```

## Known limitations

- **Deployment files are not proven on a real host.** The images were never built and the systemd
  units never started (no Docker daemon or systemd where they were written). The Compose file
  parses, the units pass `systemd-analyze verify` apart from install paths, and the Python
  environments, health probe and smoke script were run for real.
- **No TLS**, shared-secret authentication only, no rate limiting.
- **Docker does not restart an unhealthy container**; only one that exits.
- **The MCP health probe** only shows that the endpoint answers.
- **Unverified tables are unchanged since stage 1**: `durmuhurta`, `varjyam`, `gowri`,
  `functional`, `hora_generic`. Cards and MCP results depend on them and say so in `footer` and
  `unverified_tables`. See `docs/stage-1.md` for why.
- **`best` rasis ranking** sorts by day percentage, then clean share of the day, so a rasi with
  little clean time can rank highly; each row shows both figures.
- **Git tags** for both stages exist in the local repository. The session that created them could
  not push tags (the git proxy returned 403), so publishing them to GitHub is a manual step.
- `mcp` 2.x is used (`MCPServer`, not the older `FastMCP`); code samples for 1.x will not apply.
