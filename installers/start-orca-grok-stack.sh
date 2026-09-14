#!/usr/bin/env bash
# Hidden stack: Orca native MCP or CLI MCP + Cloudflare quick tunnel.
set -euo pipefail

if [[ "$(id -u)" -eq 0 ]]; then
  echo "Do not use sudo. Run as your login user."
  exit 1
fi

LISTEN="${BRIDGE_LISTEN:-127.0.0.1}"
PORT="${BRIDGE_PORT:-18783}"
CLI_PORT="${ORCA_CLI_PORT:-18784}"
WAIT_SECS="${TUNNEL_WAIT:-45}"
STATE="${GROK_ORCA_STATE:-$HOME/.grok/orca-stack}"
mkdir -p "$STATE"
LOG="$STATE/cloudflared.log"
URL_FILE="$STATE/connector.url"
PID_BRIDGE="$STATE/bridge.pid"
PID_CLI="$STATE/cli.pid"
PID_CF="$STATE/cloudflared.pid"
MODE_FILE="$STATE/mode"

resolve_root() {
  local SOURCE DIR
  SOURCE="${BASH_SOURCE[0]}"
  while [ -L "$SOURCE" ]; do
    DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
    SOURCE="$(readlink "$SOURCE")"
    [[ "$SOURCE" != /* ]] && SOURCE="${DIR}/${SOURCE}"
  done
  SCRIPT_DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
  ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
}

stop_old() {
  for f in "$PID_BRIDGE" "$PID_CLI" "$PID_CF"; do
    if [[ -f "$f" ]]; then
      kill "$(cat "$f")" 2>/dev/null || true
      rm -f "$f"
    fi
  done
}

extract_url() {
  local host
  host="$(
    grep -Eo 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG" 2>/dev/null \
      | tail -n 1 || true
  )"
  [[ -n "$host" ]] && echo "${host}/mcp"
}

probe_http() {
  local url="$1"
  python3 - "$url" <<'PY'
import sys, urllib.request
url = sys.argv[1]
try:
    urllib.request.urlopen(url, timeout=2)
    sys.exit(0)
except Exception:
    sys.exit(1)
PY
}

resolve_root
command -v cloudflared >/dev/null || {
  echo "install cloudflared: brew install cloudflare/cloudflare/cloudflared"
  exit 1
}
command -v python3 >/dev/null || { echo "python3 required"; exit 1; }

BRIDGE="${ROOT}/bridge/orca_mcp_bridge.py"
CLI="${ROOT}/mcp-server/orca_cli_mcp.py"
[[ -f "$BRIDGE" && -f "$CLI" ]] || { echo "missing bridge or CLI MCP in $ROOT"; exit 1; }

stop_old
: > "$LOG"
rm -f "$URL_FILE"

UPSTREAM="${ORCA_MCP_UPSTREAM:-}"
MODE="cli"
if [[ -n "$UPSTREAM" ]]; then
  MODE="native"
elif probe_http "http://127.0.0.1:13619/mcp"; then
  UPSTREAM="http://127.0.0.1:13619"
  MODE="native"
elif probe_http "http://127.0.0.1:13130/"; then
  echo "WARN: MaxEllis API on 13130 is REST, not MCP HTTP. Falling back to CLI MCP."
  echo "      For live GUI tools use Grok Build + uvx orcaslicer-mcp."
fi

if [[ "$MODE" == "native" ]]; then
  python3 "$BRIDGE" --listen "$LISTEN" --port "$PORT" --upstream "$UPSTREAM" \
    >/dev/null 2>"$STATE/bridge.log" &
  echo $! > "$PID_BRIDGE"
  sleep 0.4
  if ! kill -0 "$(cat "$PID_BRIDGE")" 2>/dev/null; then
    echo "bridge failed"; cat "$STATE/bridge.log"; exit 1
  fi
  TUNNEL_TARGET="http://${LISTEN}:${PORT}"
  echo "native" > "$MODE_FILE"
  echo "Mode: native MCP proxy -> $UPSTREAM"
else
  python3 "$CLI" --listen "$LISTEN" --port "$CLI_PORT" \
    >/dev/null 2>"$STATE/cli.log" &
  echo $! > "$PID_CLI"
  sleep 0.4
  if ! kill -0 "$(cat "$PID_CLI")" 2>/dev/null; then
    echo "CLI MCP failed"; cat "$STATE/cli.log"; exit 1
  fi
  python3 "$BRIDGE" --listen "$LISTEN" --port "$PORT" --upstream "http://${LISTEN}:${CLI_PORT}" \
    >/dev/null 2>"$STATE/bridge.log" &
  echo $! > "$PID_BRIDGE"
  TUNNEL_TARGET="http://${LISTEN}:${PORT}"
  echo "cli" > "$MODE_FILE"
  echo "Mode: CLI MCP (Flash Studio / stock Orca fallback)"
fi

nohup cloudflared tunnel --no-autoupdate --url "$TUNNEL_TARGET" >"$LOG" 2>&1 &
echo $! > "$PID_CF"

echo "Waiting up to ${WAIT_SECS}s for trycloudflare hostname..."
URL=""
for _ in $(seq 1 "$WAIT_SECS"); do
  URL="$(extract_url || true)"
  [[ -n "$URL" ]] && break
  sleep 1
done

if [[ -z "$URL" ]]; then
  echo "FAIL: no trycloudflare host in $LOG"
  tail -n 20 "$LOG"
  exit 1
fi

printf '%s\n' "$URL" > "$URL_FILE"
printf 'GROK_CONNECTOR_URL=%s\n' "$URL"
echo "$URL" | pbcopy 2>/dev/null || true
echo "Stop: stop-orca-grok-stack"
