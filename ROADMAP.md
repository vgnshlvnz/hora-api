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

## Stage 3: accuracy, personal card and hosting hardening (complete)
Decisions: docs/stage-3-decisions.md.
- [x] table-verification: verify durmuhurta, varjyam, gowri and functional against sources
- [x] hora-generic-source: replace the placeholder generic hora-lord table with a sourced one
- [x] vimshottari-dasha: compute dasha and bhukti periods from birth data
- [x] paksha-chandrabala: shukla-paksha handling for chandrabala houses 2, 5 and 9
- [x] personal-card: personal-windows chat card and MCP tool
- [x] docker-autorestart: restart Docker containers that fail their health check
- [x] api-tiers: per-subscriber API keys with tiers (free: day; paid: rasi, personal, profiles), profile scopes and revocation
Skipped: tls-proxy (TLS reverse proxy); not needed while OpenClaw runs on the same machine or LAN. Revisit if the API is exposed beyond the LAN.

## Stage 4: table accuracy follow-up (complete)
Decisions: docs/stage-4-decisions.md.
- [x] gowri-verification: replace the Gowri Panchangam table with Drik Panchang's (the recalled cycle was wrong) and fix the Uthi nature

## Stage 5: varjyam model (complete)
Decisions: docs/stage-5-decisions.md.
- [x] mula-varjyam-window: let a nakshatra carry more than one varjyam window, for Mula's second one

## Stage 6: sources and second checks (current)
Decisions: docs/stage-6-decisions.md.
- [ ] functional-source: replace the functional-nature table per lagna with a sourced one
- [ ] second-check: check varjyam, durmuhurta and Gowri against Drik for a second lunar month (and a second place if one is named)
- [ ] chandrabala-paksha-source: replace the placeholder paksha values for chandrabala houses 2, 5 and 9 with a sourced tradition
Skipped: host-validation (proving the deploy files on a real host); needs a host and is not in this stage.
