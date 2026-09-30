<!-- Feature state: [ ] planned, [~] in progress, [x] done. -->

## Stage 1: query API (complete)
- [x] astro-core: sunrise/sunset, nakshatra/rasi/tithi transitions
- [x] hora-engine: horas, kalams, durmuhurta, varjyam, gowri
- [x] personal-scoring: tarabala, chandrabala, hora lord rank, dasha
- [x] rasi-scoring: 12 x 24 rasi matrix
- [x] http-api: FastAPI /v1 endpoints

## Stage 2: consumers and hosting (complete)
Decisions: docs/stage-2-decisions.md.
- [x] chat-cards: API renders ready-to-show chat card payloads
- [x] mcp-server: MCP server wrapping the HTTP API
- [x] self-hosting: run the API on a personal server or home network
Skipped: esp32-client (ESP32 calls the API over the network); not part of stage 2.

## Stage 3: accuracy, personal card and hosting hardening (current)
Decisions: docs/stage-3-decisions.md.
- [~] table-verification: verify durmuhurta, varjyam, gowri and functional against sources
- [ ] hora-generic-source: replace the placeholder generic hora-lord table with a sourced one
- [x] vimshottari-dasha: compute dasha and bhukti periods from birth data
- [x] paksha-chandrabala: shukla-paksha handling for chandrabala houses 2, 5 and 9
- [x] personal-card: personal-windows chat card and MCP tool
- [x] docker-autorestart: restart Docker containers that fail their health check
- [x] api-tiers: per-subscriber API keys with tiers (free: day; paid: rasi, personal, profiles), profile scopes and revocation
Skipped: tls-proxy (TLS reverse proxy); not needed while OpenClaw runs on the same machine or LAN. Revisit if the API is exposed beyond the LAN.
