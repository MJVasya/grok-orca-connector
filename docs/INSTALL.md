# Install, run, update, remove

## New install (Mac)

1. Install a slicer:
   - Preferred for live GUI tools: [MaxEllis OrcaSlicer MCP](https://github.com/MaxEllis/OrcaSlicer/releases) or [kosmo-sys OrcaSlicer-MCP](https://github.com/kosmo-sys/OrcaSlicer-MCP/releases).
   - Or keep Flash Studio and use CLI mode.
2. `cloudflared` on PATH (`brew install cloudflare/cloudflare/cloudflared`).
3. From this repo:

```bash
bash installers/install-grok-orca.sh
```

Never `sudo`.

## After install (daily)

Do **not** rerun the installer.

1. Open the slicer (Orca MCP build, or Flash Studio for CLI-only).
2. If using MaxEllis build: Preferences → Remote API → enable → token in `ORCA_API_TOKEN`.
3. `start-orca-grok-stack` — prints `GROK_CONNECTOR_URL`.
4. grok.com/connectors → New Connector → Custom → paste URL.
5. `stop-orca-grok-stack` when done.

## Env knobs

| Var | Default | Meaning |
|---|---|---|
| `ORCA_MCP_UPSTREAM` | auto-detect `13619` then `13130` | Native `/mcp` base URL (no `/mcp` suffix) |
| `BRIDGE_PORT` | `18783` | Local bridge port |
| `ORCA_SLICER_BIN` | auto | Flash Studio / Orca binary for CLI mode |
| `ORCA_SLICER_DATA` | auto | Preset/config directory |
| `ORCA_API_TOKEN` | empty | MaxEllis Remote API |
| `GROK_ORCA_STATE` | `~/.grok/orca-stack` | PIDs + tunnel log |

## Remove

```bash
stop-orca-grok-stack
rm -rf ~/.grok/orca-stack ~/.grok/mcp/orca
# drop [mcp_servers.orcaslicer] from ~/.grok/config.toml if present
```
