# Stage 3: decisions

Stage 2 closed with these items open. They were chosen when stage 3 started.

## Decided

| Area | In stage 3 | Not in stage 3 |
| ---- | ---------- | -------------- |
| Accuracy and data | Verify the unverified tables; source the generic hora-lord table; compute Vimshottari dasha; a shukla-paksha mode for chandrabala houses 2, 5 and 9 | |
| Consumers | A personal-windows card (with an MCP tool) | More MCP tools, stdio transport, the ESP32 client |
| Hosting | Restarting unhealthy Docker containers (done) | A TLS reverse proxy (skipped, see below), remote access (VPN or tunnel), validating on a real host |

## Added after stage 3 started: subscriber access through OpenClaw

The aim is to connect the service to OpenClaw (or something similar) so that only subscribers get
the detail. Decisions:

- **Topology:** OpenClaw runs on the same machine or LAN as the API and MCP server. The API is
  not exposed to the internet, so the `tls-proxy` feature is skipped for now.
- **Gating:** enforced in both places. OpenClaw decides who may ask; the API also enforces
  tiers. That adds a feature, `api-tiers` (scope to be defined below).

Open questions this raises (none answered here):

- **What is "detail"?** Which parts of the cards and responses are free and which are paid
  (for example, sun and Moon summary free; personal windows, scored horas and blocked reasons
  paid)?
- **How does a subscriber's tier reach the API?** Today there is one shared API key and one MCP
  token, so the API cannot tell subscribers apart. Options include a key per subscriber held by
  OpenClaw, or one trusted key plus a tier or subscriber id sent per request. The MCP server
  would need a way to pass it on.
- **Keys and revocation:** where per-subscriber keys are stored, how one is revoked, and how the
  free tier is identified.
- **Profiles per subscriber:** the profiles file is single-user today. Serving several people
  means each subscriber's stored natal data, and consent and handling for it.
- **Licence:** Swiss Ephemeris is AGPL or commercial. Serving other users over a network is the
  case where that matters; it needs checking before subscribers use the service.
- **Unverified tables:** durmuhurta, varjyam, gowri, functional and hora_generic are still
  `verify: true`, and would sit behind a paid service.
- **Payments and the subscriber list:** who holds it (OpenClaw or a separate system) and how the
  API learns of changes. Not part of any planned feature.

## Still open

Questions the decisions raise. None is answered here.

- **Table verification needs sources.** Which texts or printed panchangams will be used to check
  `durmuhurta`, `varjyam`, `gowri` and `functional`, and who supplies them? Without a source a
  row stays `verify: true`. Where traditions disagree (durmuhurta especially), which one does
  the project follow?
- **Generic hora-lord table.** What is a defensible source for a generic favourability value per
  hora lord, and is a 0-1 scale still the right shape?
- **Vimshottari dasha needs the Moon's exact birth longitude**, and stored profiles hold only the
  nakshatra, rasi and lagna (no birth date or time, by rule). Where does that input come from:
  the profiles file outside the repo, the request, or a derived value stored next to the
  profile? Which year length (365.25 or 360 days) and which ayanamsa apply, and how deep
  (maha and antar, or pratyantar too)?
- **Paksha-dependent chandrabala.** Which houses count as good in shukla paksha and which in
  krishna, which tradition is followed, and is the paksha taken at the start of a hora or over
  its clean time (a tithi can change inside a hora)?
- **Personal card:** decided. It takes a stored `profile_id` only and shows best windows, why
  horas are blocked (fully blocked horas only) and tara and chandra over the day; the MCP tool
  is `hora_personal_card`. Not decided: a scored-horas section, and an inline-profile form.
- **TLS proxy:** skipped for now (see above). Revisit if the API is exposed beyond the LAN.
- **Auto-restart:** decided. An own sidecar container built from this repo (the stock autoheal
  image cannot cap restarts or write a status file), capped at 3 restarts per 30 minutes per
  container, then it gives up and records that in a status file. Not decided: alerting when it
  gives up, and the same behaviour for the systemd option (which has its own readiness timer).
- **Carried over from stage 2:** the deployment files are still unproven on a real host, and the
  ESP32 client, stdio transport and remote access are deferred.
