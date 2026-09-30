<!-- Feature state: [ ] planned, [~] in progress, [x] done. -->

## Stage 1: query API (complete)
- [x] astro-core: sunrise/sunset, nakshatra/rasi/tithi transitions
- [x] hora-engine: horas, kalams, durmuhurta, varjyam, gowri
- [x] personal-scoring: tarabala, chandrabala, hora lord rank, dasha
- [x] rasi-scoring: 12 x 24 rasi matrix
- [x] http-api: FastAPI /v1 endpoints

## Stage 2: consumers and hosting (current)
Decisions: docs/stage-2-decisions.md.
- [x] chat-cards: API renders ready-to-show chat card payloads
- [ ] mcp-server: MCP server wrapping the HTTP API
- [ ] esp32-client: ESP32 calls the API over the network
- [ ] self-hosting: run the API on a personal server or home network
