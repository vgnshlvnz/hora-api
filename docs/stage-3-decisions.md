# Stage 3: decisions

Stage 2 closed with these items open. They were chosen when stage 3 started.

## Decided

| Area | In stage 3 | Not in stage 3 |
| ---- | ---------- | -------------- |
| Accuracy and data | Verify the unverified tables; source the generic hora-lord table; compute Vimshottari dasha; a shukla-paksha mode for chandrabala houses 2, 5 and 9 | |
| Consumers | A personal-windows card (with an MCP tool) | More MCP tools, stdio transport, the ESP32 client |
| Hosting | A TLS reverse proxy on the LAN; restarting unhealthy Docker containers | Remote access (VPN or tunnel), validating on a real host |

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
- **Personal card.** Which fields does it show (top windows, the scored horas, blocked reasons,
  tara and chandra changes), and does it take a stored `profile_id` only or an inline profile
  too? The MCP tool for it follows the same answer.
- **TLS proxy.** Which proxy, which hostnames, and how are certificates issued for a private
  LAN name (an internal CA, or a local DNS name with a real CA)? How do MCP clients trust it?
  Are the plain HTTP ports still published?
- **Auto-restart.** By what mechanism (an extra container, a host timer, or a different
  runner), and how does it avoid restart loops when the profiles file is broken?
- **Carried over from stage 2:** the deployment files are still unproven on a real host, and the
  ESP32 client, stdio transport and remote access are deferred.
