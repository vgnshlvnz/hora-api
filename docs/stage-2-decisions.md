# Stage 2: decisions

Stage 1 closed with these questions open. They were answered when stage 2 started.

## Decided

| Question | Decision |
| -------- | -------- |
| MCP wrapper or direct calls | An MCP server wraps the HTTP API. The `/v1` API stays the single interface. Streamable HTTP transport, in a separate package. |
| Where chat cards are rendered | In the API. It returns ready-to-show card payloads. |
| ESP32 | Skipped for stage 2. Earlier decision: the device calls the API over the network, and the core is not ported to C. |
| Where, and whether, the API is hosted | A personal server or home network. |
| Whether to add a remote | Done: a GitHub remote exists (`vgnshlvnz/hora-api`). `main` and `stage/1` are pushed; tag pushes were blocked in the session that did it, so the tags still need pushing (see the bundle in `vgnshlvnz/hora-sample-app`). |

## Still open

Follow-on questions the decisions raise. None is answered here.

- **Chat cards:** the format is client-neutral card JSON on `/v1/cards/*`, covering the day
  summary and the rasi overview (see the README). Still open: a personal-windows card, other
  card formats for specific chat clients, and whether cards should surface more or fewer fields.
- **MCP server:** it is a separate package in `mcp-server/`, served over streamable HTTP with
  tools for the day card, rasi card and personal horas (see `mcp-server/README.md`). Still open:
  a tool for listing profiles or for inline-profile scoring, stdio as a second transport, and TLS
  for the HTTP endpoint.
- **ESP32:** skipped for stage 2, so its questions (payload, authentication, offline behaviour)
  are not being worked. Revisit in a later stage.
- **Hosting:** which machine, how is it kept running, and how is it reached from other devices
  (LAN only, VPN, tunnel)? Is TLS terminated in front of the API? Who holds the profiles file?
- **Licence:** Swiss Ephemeris is dual-licensed (AGPL or commercial). Does personal, non-public
  hosting change what needs checking?
- **Unverified tables:** `durmuhurta`, `varjyam`, `gowri`, `functional` and `hora_generic` are
  still `verify: true`. Every consumer, cards included, shows results that depend on them.
