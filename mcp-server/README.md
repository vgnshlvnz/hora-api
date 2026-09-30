# hora-mcp

An MCP server that wraps the hora-api HTTP API and serves over streamable HTTP. It is a separate
uv project with its own environment; it talks to the API over HTTP and does not import
`hora_api`.

## Tools

| Tool | Calls | Returns |
| ---- | ----- | ------- |
| `hora_day_card` | `GET /v1/cards/day` | Day card: sun, Moon, windows to avoid, Nalla Neram, horas |
| `hora_rasi_card` | `GET /v1/cards/rasi` | Rasi card: Chandrashtama rasis, best rasis, all twelve |
| `hora_personal_card` | `GET /v1/cards/personal` | Personal card: best windows, why horas are blocked, tara and chandra for a stored `profile_id` |
| `hora_personal_horas` | `GET /v1/horas/personal` | Scored horas and top windows for a stored `profile_id` |

Every tool takes optional `date`, `lat`, `lon`, `tz`, `convention` (`tamil` or `classical`) and
`ayanamsa` (`lahiri` or `kp`); omitted arguments use the API's defaults. Results are the API's
JSON unchanged. API errors (unknown profile, bad parameters, API unreachable) come back as tool
errors carrying the problem title and detail.

## Run

```
make install
HORA_API_URL=http://127.0.0.1:8000 make run     # serves http://127.0.0.1:8765/mcp
```

Start hora-api first (`make run` at the repo root). `make check` runs ruff, mypy and pytest for
this project; the root `make check` runs it too.

## Configuration (environment)

| Variable | Default | Meaning |
| -------- | ------- | ------- |
| `HORA_API_URL` | `http://127.0.0.1:8000` | The hora-api to wrap |
| `HORA_API_KEY` | none | Shared mode: sent as `X-API-Key` when the API requires keys |
| `HORA_API_TIMEOUT` | `30` | Seconds to wait for the API |
| `HORA_MCP_HOST` | `127.0.0.1` | Interface to listen on |
| `HORA_MCP_PORT` | `8765` | Port to listen on |
| `HORA_MCP_TOKEN` | none | Shared mode: clients must send `Authorization: Bearer <token>` |
| `HORA_MCP_PASSTHROUGH` | off | Passthrough mode: each caller's own hora-api key is its bearer token |
| `HORA_MCP_ALLOWED_HOSTS` | none | Comma-separated Host values accepted when not on loopback |

## Access modes

- **Shared:** `HORA_MCP_TOKEN` is the one bearer token every client uses, and `HORA_API_KEY` is the
  key this server presents to the API. Everyone behind the token gets that key's rights.
- **Passthrough:** `HORA_MCP_PASSTHROUGH=true`. Each client sends its own hora-api key as its bearer
  token; the server forwards it as `X-API-Key`, so the API applies that client's tier
  (free or paid) and profile scope, and a refused call comes back as a tool error such as
  "403 Paid tier required". The server only requires that a bearer token is present. Do not set
  `HORA_MCP_TOKEN` as well.

Listening beyond loopback without one of the two modes is refused at start-up.

## Reaching it from other machines

The default is loopback only. To serve a home network, set `HORA_MCP_HOST` (for example
`0.0.0.0`), `HORA_MCP_ALLOWED_HOSTS` (for example `hora.lan:8765,192.168.1.20:8765`, the names
clients use, otherwise requests get 421) and `HORA_MCP_TOKEN`. The MCP server can reach the
whole API with the API key it holds, so set the token whenever it listens beyond loopback. The
server speaks plain HTTP: the token and results are readable on the network unless you put TLS
in front of it.

An MCP client points at `http://<host>:8765/mcp` and sends the bearer token header.
