#!/usr/bin/env bash
# Hidden stack: native /mcp OR MaxEllis REST wrapper OR CLI MCP + Cloudflare tunnel.
set -euo pipefail

if [[ "$(id -u)" -eq 0 ]]; then
  echo "Do not use sudo. Run as your login user."
  exit 1
fi

LISTEN="${BRIDGE_LISTEN:-127.0.0.1}"
PORT="${BRIDGE_PORT:-18783}"
CLI_PORT="${ORCA_CLI_PORT:-18784}"
REMOTE_PORT="${ORCA_REMOTE_MCP_PORT:-18785}"
WAIT_SECS="${TUNNEL_WAIT:-45}"
STATE="${GROK_ORCA_STATE:-$HOME/.grok/orca-stack}"
TOKEN_FILE="${ORCA_API_TOKEN_FILE:-$HOME/.grok/orca-stack/token}"
mkdir -p "$STATE"
LOG="$STATE/cloudflared.log"
URL_FILE="$STATE/connector.url"
PID_BRIDGE="$STATE/bridge.pid"
PID_CLI="$STATE/cli.pid"
PID_REMOTE="$STATE/remote.pid"
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
  for f in "$PID_BRIDGE" "$PID_CLI" "$PID_REMOTE" "$PID_CF"; do
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

# Any HTTP response (incl. 401/404) means the port is alive.
# Only connection failures count as down.
probe_http() {
  python3 - "$1" <<'PY'
import sys
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
url = sys.argv[1]
try:
    urlopen(url, timeout=2)
    sys.exit(0)
except HTTPError:
    sys.exit(0)
except Exception:
    sys.exit(1)
PY
}

resolve_root
command -v cloudflared >/dev/null || { echo "install cloudflared"; exit 1; }
command -v python3 >/dev/null || { echo "python3 required"; exit 1; }

BRIDGE="${ROOT}/bridge/orca_mcp_bridge.py"
CLI="${ROOT}/mcp-server/orca_cli_mcp.py"
REMOTE="${ROOT}/mcp-server/orca_remote_mcp.py"
[[ -f "$BRIDGE" ]] || { echo "missing bridge"; exit 1; }
[[ -f "$REMOTE" ]] || { echo "missing remote MCP wrapper"; exit 1; }

if [[ -z "${ORCA_API_TOKEN:-}" && -f "$TOKEN_FILE" ]]; then
  ORCA_API_TOKEN="$(tr -d '[:space:]' < "$TOKEN_FILE")"
  export ORCA_API_TOKEN
fi
export ORCA_API_URL="${ORCA_API_URL:-http://127.0.0.1:13130}"

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
elif [[ -n "${ORCA_API_TOKEN:-}" ]] && probe_http "http://127.0.0.1:13130/"; then
  MODE="remote"
elif probe_http "http://127.0.0.1:13130/"; then
  echo "WARN: :13130 up but ORCA_API_TOKEN unset."
  echo "      echo TOKEN > $TOKEN_FILE"
  echo "      Falling back to CLI MCP (no live GUI)."
fi

start_bridge() {
  local up="$1"
  python3 "$BRIDGE" --listen "$LISTEN" --port "$PORT" --upstream "$up" \
    >/dev/null 2>"$STATE/bridge.log" &
  echo $! > "$PID_BRIDGE"
  sleep 0.4
  if ! kill -0 "$(cat "$PID_BRIDGE")" 2>/dev/null; then
    echo "bridge failed"; cat "$STATE/bridge.log"; exit 1
  fi
}

if [[ "$MODE" == "native" ]]; then
  start_bridge "$UPSTREAM"
  echo "native" > "$MODE_FILE"
  echo "Mode: native MCP proxy -> $UPSTREAM"
elif [[ "$MODE" == "remote" ]]; then
  python3 "$REMOTE" --listen "$LISTEN" --port "$REMOTE_PORT" \
    >/dev/null 2>"$STATE/remote.log" &
  echo $! > "$PID_REMOTE"
  sleep 0.4
  if ! kill -0 "$(cat "$PID_REMOTE")" 2>/dev/null; then
    echo "remote MCP failed"; cat "$STATE/remote.log"; exit 1
  fi
  start_bridge "http://${LISTEN}:${REMOTE_PORT}"
  echo "remote" > "$MODE_FILE"
  echo "Mode: MaxEllis Remote API HTTP-MCP wrapper -> $ORCA_API_URL"
else
  python3 "$CLI" --listen "$LISTEN" --port "$CLI_PORT" \
    >/dev/null 2>"$STATE/cli.log" &
  echo $! > "$PID_CLI"
  sleep 0.4
  if ! kill -0 "$(cat "$PID_CLI")" 2>/dev/null; then
    echo "CLI MCP failed"; cat "$STATE/cli.log"; exit 1
  fi
  start_bridge "http://${LISTEN}:${CLI_PORT}"
  echo "cli" > "$MODE_FILE"
  echo "Mode: CLI MCP (no live GUI)"
fi

nohup cloudflared tunnel --no-autoupdate --url "http://${LISTEN}:${PORT}" >"$LOG" 2>&1 &
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
