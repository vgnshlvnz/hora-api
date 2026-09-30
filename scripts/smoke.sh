#!/usr/bin/env bash
# Smoke test for a running deployment: API health, one day card, and one MCP tool call.
# Needs curl and python3 (JSON parsing only). Exit status 0 if every check passes.
#
#   HORA_API_URL     API base URL           (default http://127.0.0.1:8000)
#   HORA_API_KEY     X-API-Key, if auth is on
#   HORA_MCP_URL     MCP endpoint           (default http://127.0.0.1:8765/mcp)
#   HORA_MCP_TOKEN   bearer token, if set on the MCP server
#   SKIP_MCP=1       skip the MCP checks
#   REQUIRE_AUTH=1   fail (instead of warn) if the API answers without a key
#   WATCHER_STATUS_FILE  the watcher's status file (deploy/watcher-status/watcher.json); if set,
#                    check it is fresh and no container was given up on
#
# The day card is the golden Petaling Jaya day (Wed 2026-09-30, Lahiri, tamil), so the checks
# assert known values; they do not depend on today's date.
set -u

API=${HORA_API_URL:-http://127.0.0.1:8000}
API=${API%/}
MCP=${HORA_MCP_URL:-http://127.0.0.1:8765/mcp}
QUERY="date=2026-09-30&lat=3.107&lon=101.606&tz=Asia/Kuala_Lumpur"

fails=0
pass() { printf 'PASS  %s\n' "$1"; }
warn() { printf 'WARN  %s\n' "$1"; }
fail() { printf 'FAIL  %s\n' "$1"; fails=$((fails + 1)); }

api_key=()
[[ -n ${HORA_API_KEY:-} ]] && api_key=(-H "X-API-Key: $HORA_API_KEY")

# json_get <python expression over `d`> : reads JSON on stdin, prints the expression's value.
json_get() { python3 -c 'import json,sys; d=json.load(sys.stdin); print(eval(sys.argv[1]))' "$1" 2>/dev/null; }

# --- API ---------------------------------------------------------------------------------
body=$(curl -fsS --max-time 10 "$API/healthz" 2>&1) && [[ $(json_get 'd["status"]' <<<"$body") == ok ]] \
  && pass "API /healthz" || fail "API /healthz ($body)"

body=$(curl -sS --max-time 10 "$API/readyz" 2>&1)
if [[ $(json_get 'd["status"]' <<<"$body") == ready ]]; then
  pass "API /readyz (profiles: $(json_get 'd["profiles"]' <<<"$body"))"
else
  fail "API /readyz not ready: $body"
fi

code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$API/v1/profiles")
if [[ $code == 401 ]]; then
  pass "API rejects requests without a key (401)"
elif [[ $code == 000 ]]; then
  :  # unreachable: already reported above
elif [[ ${REQUIRE_AUTH:-0} == 1 ]]; then
  fail "API answered $code without a key; API_KEYS is not enforced"
else
  warn "API answered $code without a key; auth looks OFF (fine locally, not on a LAN)"
fi

card=$(curl -fsS --max-time 30 "${api_key[@]}" "$API/v1/cards/day?$QUERY" 2>&1)
if [[ $(json_get 'd["kind"] + "|" + d["title"]' <<<"$card") == "day|Wednesday 30 Sep 2026" ]]; then
  sunrise=$(json_get '[r["value"] for s in d["sections"] if s["id"]=="sun" for r in s["rows"] if r["label"]=="Sunrise"][0]' <<<"$card")
  moon=$(json_get '[r["value"] for s in d["sections"] if s["id"]=="moon" for r in s["rows"] if r["label"]=="Nakshatra"][0]' <<<"$card")
  if [[ $sunrise == 07:02 && $moon == "Bharani → Krittika"* ]]; then
    pass "API day card (sunrise $sunrise, nakshatra $moon)"
  else
    fail "API day card has unexpected values (sunrise '$sunrise', nakshatra '$moon')"
  fi
else
  fail "API day card request failed: ${card:0:200}"
fi

code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "${api_key[@]}" "$API/v1/profiles")
[[ $code == 200 ]] && pass "API /v1/profiles" || fail "API /v1/profiles returned $code"

# --- Watcher -----------------------------------------------------------------------------
if [[ -n ${WATCHER_STATUS_FILE:-} ]]; then
  if [[ -r $WATCHER_STATUS_FILE ]]; then
    verdict=$(python3 - "$WATCHER_STATUS_FILE" <<'PY'
import json, sys, time
d = json.load(open(sys.argv[1]))
age = time.time() - d["updated_epoch"]
stale = age > 3 * d["policy"]["interval_seconds"]
gave_up = [n for n, s in d["services"].items() if s["state"] == "gave_up"]
if d.get("docker_error"):
    print("FAIL|watcher cannot reach Docker: " + d["docker_error"])
elif stale:
    print("FAIL|watcher status is stale (%.0fs old)" % age)
elif gave_up:
    print("FAIL|watcher gave up restarting: " + ", ".join(gave_up))
else:
    print("PASS|watcher status fresh; restarts in window: " + str(sum(s["restarts_in_window"] for s in d["services"].values())))
PY
)
    case ${verdict%%|*} in
      PASS) pass "${verdict#*|}" ;;
      *) fail "${verdict#*|}" ;;
    esac
  else
    fail "WATCHER_STATUS_FILE $WATCHER_STATUS_FILE is not readable"
  fi
fi

# --- MCP ---------------------------------------------------------------------------------
if [[ ${SKIP_MCP:-0} != 1 ]]; then
  mcp_h=(-H "Content-Type: application/json" -H "Accept: application/json, text/event-stream")
  [[ -n ${HORA_MCP_TOKEN:-} ]] && mcp_h+=(-H "Authorization: Bearer $HORA_MCP_TOKEN")

  # Streamable HTTP replies are server-sent events ("data: {json}") or plain JSON.
  payload() { sed -n 's/^data: *//p' | tail -n 1 | grep . || cat; }

  hdr=$(mktemp)
  trap 'rm -f "$hdr"' EXIT
  init='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"smoke","version":"0"}}}'
  resp=$(curl -sS --max-time 15 -D "$hdr" "${mcp_h[@]}" -X POST "$MCP" -d "$init" 2>&1 | payload)
  if [[ $(json_get 'd["result"]["serverInfo"]["name"]' <<<"$resp") == hora-api ]]; then
    pass "MCP initialize"
    session=$(tr -d '\r' <"$hdr" | sed -n 's/^[Mm]cp-[Ss]ession-[Ii]d: *//p' | head -n 1)
    [[ -n $session ]] && mcp_h+=(-H "Mcp-Session-Id: $session")
    curl -sS --max-time 15 -o /dev/null "${mcp_h[@]}" -X POST "$MCP" \
      -d '{"jsonrpc":"2.0","method":"notifications/initialized"}'

    tools=$(curl -sS --max-time 15 "${mcp_h[@]}" -X POST "$MCP" \
      -d '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' | payload)
    names=$(json_get '",".join(sorted(t["name"] for t in d["result"]["tools"]))' <<<"$tools")
    if [[ $names == hora_day_card,hora_personal_card,hora_personal_horas,hora_rasi_card ]]; then
      pass "MCP tools/list ($names)"
    else
      fail "MCP tools/list returned '$names'"
    fi

    call='{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"hora_day_card","arguments":{"date":"2026-09-30","lat":3.107,"lon":101.606,"tz":"Asia/Kuala_Lumpur"}}}'
    out=$(curl -sS --max-time 45 "${mcp_h[@]}" -X POST "$MCP" -d "$call" | payload)
    title=$(json_get 'd["result"]["structuredContent"]["title"] if not d["result"].get("isError") else "ERROR: " + d["result"]["content"][0]["text"]' <<<"$out")
    if [[ $title == "Wednesday 30 Sep 2026" ]]; then
      pass "MCP hora_day_card ($title)"
    else
      fail "MCP hora_day_card: ${title:-no result}"
    fi
  else
    fail "MCP initialize failed: ${resp:0:200}"
  fi

  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "${mcp_h[@]:0:4}" -X POST "$MCP" -d "$init")
  if [[ -n ${HORA_MCP_TOKEN:-} ]]; then
    [[ $code == 401 ]] && pass "MCP rejects requests without the token (401)" \
      || fail "MCP answered $code without the token; HORA_MCP_TOKEN is not enforced"
  fi
fi

echo
if ((fails)); then echo "$fails check(s) failed"; exit 1; fi
echo "all checks passed"
