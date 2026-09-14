#!/usr/bin/env bash
# Stop Orca Grok stack. Does not touch Fusion cloudflared (:18782).
set -u
STATE="${GROK_ORCA_STATE:-$HOME/.grok/orca-stack}"
PORT="${BRIDGE_PORT:-18783}"

kill_pidfile() {
  local f="$1" pid
  [[ -f "$f" ]] || return 0
  pid="$(tr -d '[:space:]' < "$f")"
  rm -f "$f"
  [[ "$pid" =~ ^[0-9]+$ ]] || return 0
  kill -TERM "$pid" 2>/dev/null || true
  sleep 0.2
  kill -KILL "$pid" 2>/dev/null || true
}

for f in "$STATE/bridge.pid" "$STATE/cli.pid" "$STATE/remote.pid" "$STATE/cloudflared.pid"; do
  kill_pidfile "$f"
done

# Orphans: only tunnels whose argv mentions the Orca bridge port.
if command -v pgrep >/dev/null; then
  while read -r pid; do
    [[ -n "$pid" ]] || continue
    kill -TERM "$pid" 2>/dev/null || true
  done < <(pgrep -f "cloudflared.*tunnel.*:${PORT}" || true)
  sleep 0.3
  while read -r pid; do
    [[ -n "$pid" ]] || continue
    kill -KILL "$pid" 2>/dev/null || true
  done < <(pgrep -f "cloudflared.*tunnel.*:${PORT}" || true)
fi

# Python listeners on Orca ports
for p in "$PORT" "${ORCA_CLI_PORT:-18784}" "${ORCA_REMOTE_MCP_PORT:-18785}"; do
  if command -v lsof >/dev/null; then
    lsof -nP -iTCP:"$p" -sTCP:LISTEN -t 2>/dev/null | while read -r pid; do
      kill -TERM "$pid" 2>/dev/null || true
    done
  fi
done

echo "orca grok stack stopped"
if command -v pgrep >/dev/null && pgrep -lf cloudflared >/dev/null 2>&1; then
  echo "note: other cloudflared still running (e.g. Fusion). Orca :${PORT} should be gone."
  pgrep -lf cloudflared || true
fi
