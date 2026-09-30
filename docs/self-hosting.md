# Self-hosting on a home server

Runs the API (port 8000) and the MCP server (port 8765, endpoint `/mcp`) on one machine, reached
from other devices on the LAN over plain HTTP. Two ways to run it: Docker Compose, or systemd
units. Pick one per machine.

## Read this first: what "LAN only, plain HTTP" means

- Anyone on the network can read traffic, including API keys and the MCP bearer token. Do not
  expose either port to the internet, and do not port-forward them.
- Both services therefore require credentials: keys for the API (`X-API-Key` header) and, for the
  MCP server, either one shared `HORA_MCP_TOKEN` or each caller's own key (`HORA_MCP_PASSTHROUGH`).
  The Compose file refuses to start without `API_KEYS`, and the MCP server refuses to listen
  beyond loopback without one of its two access modes. In shared mode the MCP server holds an
  API key, so its token is as sensitive as that key.
- Put TLS in front later if you need it; nothing here rules that out.
- The API answers about a date and place, and stored profiles hold a person's nakshatra, rasi
  and lagna. Treat the profiles file as personal data (see "Profiles").
- Three tables are unverified (`durmuhurta`, `varjyam`, `gowri`; `functional` and `hora_generic`
  too, for scoring). Responses list them in `unverified_tables`. See `docs/stage-1.md`.

## Files

| Path | Purpose |
| ---- | ------- |
| `deploy/Dockerfile` | One file, two targets: `api` and `mcp` |
| `deploy/docker-compose.yml` | Runs both, with health checks and restart |
| `deploy/env.example` | Compose settings; copy to `deploy/.env` (git-ignored) |
| `deploy/healthcheck.py` | Container health probe (`api` uses `/readyz`, `mcp` checks it answers) |
| `deploy/watcher.py` | Sidecar that restarts unhealthy containers, with a cap and a status file |
| `deploy/systemd/*.service`, `*.timer` | systemd units and the readiness timer |
| `deploy/systemd/*.env.example` | systemd environment files |
| `scripts/smoke.sh` | Post-deploy check of health, a day card and an MCP call |

## Configuration

| Variable | Used by | Meaning |
| -------- | ------- | ------- |
| `API_KEYS` | API | Owner keys accepted in `X-API-Key` (paid tier, every profile) |
| `KEYS_PATH` | API | Per-subscriber keys file with tiers and profile scopes (`KEYS_DIR` in Compose) |
| `PROFILES_PATH` | API | Profiles file (systemd; Compose mounts it at `/profiles/profiles.yaml`) |
| `DEFAULT_LAT`, `DEFAULT_LON`, `DEFAULT_TZ` | API | Place used when a request omits it |
| `HORA_BIND`, `HORA_PORT` | systemd API unit | uvicorn interface and port |
| `HORA_API_URL` | MCP | The API to wrap (`http://api:8000` in Compose) |
| `HORA_API_KEY` | MCP | Shared mode: one of the keys in `API_KEYS` |
| `HORA_MCP_PASSTHROUGH` | MCP | Passthrough mode: each caller's own key is the bearer token |
| `HORA_MCP_HOST`, `HORA_MCP_PORT` | MCP | Where it listens |
| `HORA_MCP_TOKEN` | MCP | Shared mode: the one bearer token clients must send |
| `HORA_MCP_ALLOWED_HOSTS` | MCP | Host values accepted, for example `hora.lan:8765`; empty disables the Host check |
| `PROFILES_DIR`, `API_PUBLISH`, `MCP_PUBLISH` | Compose | Host directory for profiles, and publish addresses |
| `DOCKER_GID` | Compose | Group that owns the Docker socket (`stat -c %g /var/run/docker.sock`); required |
| `WATCHER_STATUS_DIR` | Compose | Host directory for the watcher's status file (default `deploy/watcher-status`) |
| `WATCHER_INTERVAL`, `WATCHER_MAX_RESTARTS`, `WATCHER_WINDOW` | Watcher | Poll seconds (15), restarts allowed per window (3), window seconds (1800) |

Generate secrets with `openssl rand -hex 24`.

## Option A: Docker Compose

Needs Docker with the Compose plugin.

```
git clone https://github.com/vgnshlvnz/hora-api /opt/hora-api && cd /opt/hora-api
mkdir -p /srv/hora-api/profiles          # see "Profiles" for the file itself
cp deploy/env.example deploy/.env        # edit: PROFILES_DIR, API_KEYS, HORA_API_KEY, HORA_MCP_TOKEN
cd deploy && docker compose up -d --build
docker compose ps                         # both services should become "healthy"
```

- **Health:** the API reports healthy when `/readyz` returns 200 (ephemeris answers and the
  profiles file loads). The MCP container is healthy when its endpoint answers. `mcp` starts
  after `api` is healthy. Docker restarts a container that exits (`restart: unless-stopped`) but
  not one that is merely unhealthy; the `watcher` service below does that.
- **Narrow the listening address:** set `API_PUBLISH=192.168.1.20:8000` and
  `MCP_PUBLISH=192.168.1.20:8765` in `deploy/.env` to publish on one interface only.
- **Profiles readable by the container:** the container user has uid 10001, so
  `chmod 644 profiles.yaml` (or `chown 10001` it) and keep the directory listable.
- **Logs:** `docker compose logs -f api mcp`.

### Restarting unhealthy containers (the watcher)

The `watcher` service polls Docker every 15 seconds and restarts any container labelled
`hora.autorestart=true` (the API and MCP server) whose health check says "unhealthy".

- **Capped.** At most 3 restarts per 30 minutes per container (`WATCHER_MAX_RESTARTS`,
  `WATCHER_WINDOW`). A restart does not fix everything (a broken profiles file keeps `/readyz`
  failing), so when the cap is reached the watcher **gives up** on that container: it logs an
  error once, stops restarting it, and keeps watching. When the container is healthy again
  (for example after you fix the profiles file and it reloads) the watcher notes the recovery and
  its budget applies afresh from the restarts still inside the window.
- **Status file.** Every poll it writes `deploy/watcher-status/watcher.json`: `ok` (false if it
  gave up on anything or cannot reach Docker), when it was updated, and per container the state
  (`ok`, `starting`, `restarting`, `gave_up`, `stopped`), restart count and times. It also holds
  the restart history, so a restarted watcher does not start over with a full budget.
- **Set up.**
  ```
  stat -c %g /var/run/docker.sock              # put this number in deploy/.env as DOCKER_GID
  mkdir -p deploy/watcher-status && sudo chown 10001:10001 deploy/watcher-status
  cd deploy && docker compose up -d --build
  cat watcher-status/watcher.json ; docker compose logs -f watcher
  ```
  Point `scripts/smoke.sh` at it with `WATCHER_STATUS_FILE=deploy/watcher-status/watcher.json` to
  fail when the file is stale, Docker is unreachable, or a container was given up on.
- **Security: it mounts the Docker socket.** Anything that can use the socket controls Docker,
  which is root-equivalent on the host. The watcher runs as a non-root user with a read-only
  filesystem, no capabilities and `no-new-privileges`, uses only the standard library, and its
  code only lists labelled containers, inspects them and restarts them. Even so, treat it as
  trusted. To run without it, start only the app services (`docker compose up -d api mcp`).
- **Not a monitor.** After giving up it does not alert anyone. Check the status file (the smoke
  script does) or the logs.

## Option B: systemd

Needs Python 3.12, `uv`, `curl` and systemd on the host.

```
useradd --system --home-dir /opt/hora-api --shell /usr/sbin/nologin hora
git clone https://github.com/vgnshlvnz/hora-api /opt/hora-api
cd /opt/hora-api && uv sync --frozen --no-dev
cd mcp-server && uv sync --frozen --no-dev && cd ..
chown -R hora:hora /opt/hora-api

install -d -m 750 -o root -g hora /etc/hora-api
install -m 640 -o root -g hora deploy/systemd/hora-api.env.example /etc/hora-api/hora-api.env
install -m 640 -o root -g hora deploy/systemd/hora-mcp.env.example /etc/hora-api/hora-mcp.env
$EDITOR /etc/hora-api/hora-api.env /etc/hora-api/hora-mcp.env    # keys, token, place

cp deploy/systemd/hora-*.service deploy/systemd/hora-healthcheck.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now hora-api hora-mcp hora-healthcheck.timer
```

- **Health and restart:** `Restart=on-failure` restarts a crashed process. systemd has no HTTP
  health check, so `hora-healthcheck.timer` runs every minute: if `/readyz` fails it restarts
  `hora-api`. It does nothing while the API is stopped on purpose.
- **Logs:** `journalctl -u hora-api -u hora-mcp -f`. Status: `systemctl status hora-api hora-mcp`.

## Subscribers, tiers and keys

For serving more than one person (for example subscribers reached through an assistant such as
OpenClaw running on the same machine or LAN) each person gets their own key.

| Tier | Endpoints |
| ---- | --------- |
| free | `GET /v1/day`, `GET /v1/cards/day` |
| paid | everything else: `/v1/horas/rasi`, `/v1/cards/rasi`, `/v1/horas/personal` (GET and POST), `/v1/cards/personal`, `/v1/profiles` |

`/healthz` and `/readyz` need no key. A free key on a paid endpoint gets a 403 problem
(`urn:hora-api:problem:tier-required`, with `tier` and `required_tier`). A missing, unknown or
revoked key gets 401.

**The keys file** (`KEYS_PATH`, outside the repo, mode 600) holds one entry per key. The key
itself is never stored, only its SHA-256:

```yaml
keys:
  - id: alice
    hash: sha256:...
    tier: paid
    profiles: [alice-me, alice-partner]   # stored profile ids this key may use; "*" means all
    revoked: false
```

Manage it with `hora-keys` (installed with the project; `uv run hora-keys ...`):

```
hora-keys --file /etc/hora-api/keys.yaml add --id alice --tier paid --profiles alice-me
hora-keys --file /etc/hora-api/keys.yaml list          # ids, tiers, state; never keys or hashes
hora-keys --file /etc/hora-api/keys.yaml revoke alice  # takes effect on the next request
hora-keys --file /etc/hora-api/keys.yaml restore alice
```

`add` prints the key **once**; hand it to the subscriber and do not lose it, because it cannot be
shown again. The file is re-read when it changes, so no restart is needed to add, downgrade or
revoke. With Compose the keys directory is mounted read-only, so run `hora-keys` on the host
against `deploy/keys/keys.yaml` (or wherever `KEYS_DIR` points).

- **Profile scope.** A key sees and uses only the stored profiles it lists. Anything else looks
  exactly like a profile that does not exist (404). A paid key with no `profiles` can still send
  an inline profile with `POST /v1/horas/personal`; nothing in the body is stored.
- **Owner keys.** Keys in `API_KEYS` keep working as owner keys (paid, every profile), for you or
  an admin tool.
- **Authentication is on as soon as any key exists** (in `API_KEYS` or the file, even a revoked
  one). If the keys file cannot be read, requests get 503 rather than being let through, and
  `/readyz` fails.
- **Logs** show the key's `id`, never the key.

**Through the MCP server.** Set `HORA_MCP_PASSTHROUGH=true` (and drop `HORA_MCP_TOKEN` and
`HORA_API_KEY`): each caller sends its own hora-api key as its bearer token, the MCP server
forwards it as `X-API-Key`, and hora-api applies that caller's tier and profile scope. The MCP
server only insists that a bearer token is present; hora-api decides whether it is valid. In shared
mode (`HORA_MCP_TOKEN`) every caller behind the token gets the rights of the one upstream key.
The assistant that fronts your subscribers must hold each subscriber's key and present the right
one per request; deciding who is a subscriber stays with it.

## Profiles

The API reads profiles from `PROFILES_PATH` and reloads the file when it changes, so edits need
no restart. A bad file makes `/readyz` return 503 and `/v1/profiles` return a 503 problem.

```yaml
profiles:
  - id: me
    display_name: Me
    janma_nakshatra: Rohini
    janma_rasi: Vrishabha
    lagna: Kumbha
    tz_home: Asia/Kuala_Lumpur
```

- Real profiles never go in the repository. Compose keeps them under `PROFILES_DIR`
  (for example `/srv/hora-api/profiles/profiles.yaml`); systemd uses
  `/etc/hora-api/profiles.yaml` (`chmod 640`, owner `root:hora`).
- The file holds derived natal data (nakshatra, rasi, lagna). A profile may also carry an
  optional `birth_datetime` (with a UTC offset, for example `2026-03-24T05:30:00+08:00`); the API
  then computes Vimshottari dasha and bhukti periods from the Moon's position at that moment.
  **That is a real birth time, so the file is more sensitive with it.** Only add it if you want
  computed dasha, keep the file mode `640`, and encrypt every copy that leaves the machine. The
  API never returns it: `/v1/profiles` lists ids and display names only, and no card or scored
  response includes it. A profile can instead list `dasha` periods explicitly, which take
  precedence.
- **Back up** the single file: `cp -p profiles.yaml profiles.yaml.$(date +%F)` into a location
  outside the repo, and include it in the machine's normal backups. If the backup leaves the
  machine, encrypt it (for example with `age` or `gpg`).
- **Restore** by copying the file back to the same path with the same owner and mode. The API
  picks it up within a request or two; check with `curl -H "X-API-Key: $KEY" $API/v1/profiles`.

## Check a deployment

```
HORA_API_URL=http://hora.lan:8000 HORA_API_KEY=... \
HORA_MCP_URL=http://hora.lan:8765/mcp HORA_MCP_TOKEN=... scripts/smoke.sh
```

It checks `/healthz` and `/readyz`, that a request without a key is rejected, the golden
Petaling Jaya day card (sunrise 07:02, Bharani to Krittika), the profiles list, and over MCP:
`initialize`, `tools/list`, a `hora_day_card` call, and that the token is enforced. It exits 1 if
anything fails. Set `REQUIRE_AUTH=1` to fail when the API answers without a key, `SKIP_MCP=1`, or `FREE_KEY=...`
(with a paid or owner key in `HORA_API_KEY`) to check that a free key gets the day card and a 403 on
paid endpoints.

## Upgrade and roll back

Releases are tagged (`v0.1.0` and later `vX.Y.0`).

```
cd /opt/hora-api && git fetch --tags && git checkout v0.2.0    # the tag you want

# Compose
cd deploy && docker compose up -d --build

# systemd
cd /opt/hora-api && uv sync --frozen --no-dev
(cd mcp-server && uv sync --frozen --no-dev)
systemctl restart hora-api hora-mcp
```

Then run `scripts/smoke.sh`. To roll back, check out the previous tag and repeat the same steps.
Configuration and profiles live outside the checkout, so they are unaffected.

## Troubleshooting

| Symptom | Likely cause |
| ------- | ------------ |
| Compose stops with "required variable ... is missing" | `deploy/.env` lacks `API_KEYS`, `HORA_API_KEY`, `HORA_MCP_TOKEN` or `PROFILES_DIR` |
| API 401 | Missing, wrong or revoked `X-API-Key` |
| API 403 `tier-required` | A free key on a paid endpoint; upgrade the key with `hora-keys` |
| API 503 `keys-unavailable` | The keys file is unreadable or invalid YAML; requests fail closed until it is fixed |
| Profile 404 for a profile that exists | The key's `profiles` list does not include it |
| MCP 401 | Missing or wrong bearer token |
| MCP 421 (misdirected request) | The name clients use is not in `HORA_MCP_ALLOWED_HOSTS` (include the port) |
| `/readyz` 503 | Profiles file missing permissions, or invalid YAML; see the API log |
| Container unhealthy, `mcp` never starts | `api` is not healthy yet; check `docker compose logs api` |
| Watcher log: `gave_up` | Restarting did not help; find the cause in `docker compose logs api` (often the profiles file), fix it, and the watcher resumes when the container is healthy |
| Watcher unhealthy or `docker_error` in the status file | Wrong `DOCKER_GID` (permission denied on the socket), or the socket path is not `/var/run/docker.sock` |
| Watcher cannot write the status file | `deploy/watcher-status` is not writable by uid 10001 |
| MCP tool error "cannot reach hora-api" | Wrong `HORA_API_URL`, or the API is down |
| Profile name errors ("unknown nakshatra") | Use classical names such as `Rohini`, or indices 0-26 |
| Times off by hours | Pass the `tz` parameter or set `DEFAULT_TZ` |

## Known limits

- The Docker images and systemd units were written and checked for syntax here, but not built or
  started on a real host: this environment has no Docker daemon or systemd. The Python
  environments the images install (`uv sync --frozen --no-dev`), the health probe, the
  compose file (`docker compose config`) and `scripts/smoke.sh` were run for real. Do a first
  deployment with the smoke test in hand.
- Plain HTTP, shared-secret auth only, no rate limiting.
- The watcher needs the Docker socket (see its security note) and only restarts; it does not
  alert. It was tested against a fake Docker Engine API over a unix socket, not a real daemon.
- The MCP health probe only shows the endpoint answers, not that the API behind it works.
