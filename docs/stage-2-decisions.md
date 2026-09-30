# Stage 2: decisions

Stage 1 closed with these questions open. They were answered when stage 2 started.

## Decided

| Question | Decision |
| -------- | -------- |
| MCP wrapper or direct calls | An MCP server wraps the HTTP API. The `/v1` API stays the single interface. |
| Where chat cards are rendered | In the API. It returns ready-to-show card payloads. |
| ESP32 | The device calls the API over the network. The core is not ported to C. |
| Where, and whether, the API is hosted | A personal server or home network. |
| Whether to add a remote | Done: a GitHub remote exists (`vgnshlvnz/hora-api`). `main` and `stage/1` are pushed; tag pushes were blocked in the session that did it, so the tags still need pushing (see the bundle in `vgnshlvnz/hora-sample-app`). |

## Still open

Follow-on questions the decisions raise. None is answered here.

- **Chat cards:** the format is client-neutral card JSON on `/v1/cards/*`, covering the day
  summary and the rasi overview (see the README). Still open: a personal-windows card, other
  card formats for specific chat clients, and whether cards should surface more or fewer fields.
- **MCP server:** stdio or HTTP transport? Which tools does it expose, and how does it hold the
  API key and base URL?
- **ESP32:** what payload does a constrained device fetch (a compact or pre-rendered response)?
  How does it authenticate, and how does it behave when the API is unreachable?
- **Hosting:** which machine, how is it kept running, and how is it reached from other devices
  (LAN only, VPN, tunnel)? Is TLS terminated in front of the API? Who holds the profiles file?
- **Licence:** Swiss Ephemeris is dual-licensed (AGPL or commercial). Does personal, non-public
  hosting change what needs checking?
- **Unverified tables:** `durmuhurta`, `varjyam`, `gowri`, `functional` and `hora_generic` are
  still `verify: true`. Every consumer, cards included, shows results that depend on them.
