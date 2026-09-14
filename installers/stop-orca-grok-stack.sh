#!/usr/bin/env bash
set -euo pipefail
STATE="${GROK_ORCA_STATE:-$HOME/.grok/orca-stack}"
for f in "$STATE/bridge.pid" "$STATE/cli.pid" "$STATE/remote.pid" "$STATE/cloudflared.pid"; do
  if [[ -f "$f" ]]; then
    kill "$(cat "$f")" 2>/dev/null || true
    rm -f "$f"
  fi
done
echo "orca grok stack stopped"
