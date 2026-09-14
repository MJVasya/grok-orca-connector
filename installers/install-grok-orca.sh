#!/usr/bin/env bash
set -euo pipefail

if [[ "$(id -u)" -eq 0 ]]; then
  echo "Do not use sudo. Run as your login user so files land in ~/.grok"
  exit 1
fi

CONNECTOR_DIR="${HOME}/.grok/mcp/orca"
BIN_DIR="${HOME}/.grok/bin"
mkdir -p "$CONNECTOR_DIR" "$BIN_DIR"

SOURCE="${BASH_SOURCE[0]}"
while [ -L "$SOURCE" ]; do
  DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
  SOURCE="$(readlink "$SOURCE")"
  [[ "$SOURCE" != /* ]] && SOURCE="${DIR}/${SOURCE}"
done
SCRIPT_DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "== Grok Orca MCP installer =="
echo "Repo: $ROOT"

ln -sfn "$ROOT/installers/start-orca-grok-stack.sh" "$BIN_DIR/start-orca-grok-stack"
ln -sfn "$ROOT/installers/stop-orca-grok-stack.sh" "$BIN_DIR/stop-orca-grok-stack"
chmod +x "$ROOT/installers/"*.sh "$ROOT/bridge/"*.py "$ROOT/mcp-server/"*.py || true

export PATH="$BIN_DIR:$PATH"
if ! grep -q '.grok/bin' "${HOME}/.zprofile" 2>/dev/null; then
  echo 'export PATH="$HOME/.grok/bin:$PATH"' >> "${HOME}/.zprofile"
  echo "Appended PATH to ~/.zprofile"
fi

cat > "${CONNECTOR_DIR}/manifest.json" << EOF
{
  "name": "orcaslicer",
  "version": "1.0.0",
  "description": "OrcaSlicer / Flash Studio MCP for Grok",
  "transport": { "type": "http", "url": "http://127.0.0.1:18783/mcp" }
}
EOF

TOML="${HOME}/.grok/config.toml"
mkdir -p "${HOME}/.grok"
if [[ -f "$TOML" ]] && grep -q '\[mcp_servers.orcaslicer\]' "$TOML"; then
  echo "config.toml already has [mcp_servers.orcaslicer]"
else
  printf '\n[mcp_servers.orcaslicer]\nurl = "http://127.0.0.1:18783/mcp"\n' >> "$TOML"
  echo "Wrote ${TOML} [mcp_servers.orcaslicer]"
fi

if command -v grok >/dev/null 2>&1; then
  grok mcp add --transport http orcaslicer "http://127.0.0.1:18783/mcp" >/dev/null 2>&1 || true
fi

echo
echo "Next: start-orca-grok-stack"
echo "Stop: stop-orca-grok-stack"
echo "Add $BIN_DIR to PATH in this shell if the commands are not found."
