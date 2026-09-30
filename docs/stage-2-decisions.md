# Stage 2: open decisions

Stage 2 is undecided. These questions are open; none is answered here. `stage/2` is not created
until they are.

## Consumers

1. **MCP wrapper or direct calls.** Should an MCP server wrap the HTTP API, expose the Python
   core directly, or should clients call the HTTP API without MCP?
2. **Where chat cards are rendered.** In the API, in an MCP tool result, in the chat client, or
   elsewhere? Which formats and which chat clients?
3. **ESP32.** Does the device call the API over the network, or is the core ported to C? What
   happens when it is offline?

## Hosting

4. **Where, and whether, the API is hosted.** Local only, a personal server, or a cloud service?
   Who may call it, and how do keys and TLS work in that case?
5. **Whether to add a remote.** The repository has no remote and nothing is pushed. Should it get
   one, where, and public or private?

## Inputs to the decisions

Facts from stage 1 that bear on the questions above; they are not recommendations.

- The API is stateless apart from an in-memory cache; profiles come from a file outside the repo.
- Swiss Ephemeris (via pyswisseph) is dual-licensed AGPL or commercial. This applies to hosting
  the API and to any port of the core.
- Five tables are unverified (see `docs/stage-1.md`). Any consumer shows results that depend on
  them.
- The core (`hora_api.core`) is pure Python with no I/O or FastAPI imports.
- Auth is an optional shared key in a header; there is no TLS termination or rate limiting.
