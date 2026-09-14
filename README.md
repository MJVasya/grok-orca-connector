# Grok Orca MCP Connector

Sibling of [grok-fusion-connector](https://github.com/MJVasya/grok-fusion-connector).
Same pattern: local MCP → Host-rewrite bridge → Cloudflare quick tunnel → `GROK_CONNECTOR_URL` for [grok.com/connectors](https://grok.com/connectors) Custom.

Flash Studio Desktop (Orca-Flashforge fork, e.g. v1.7.17) has **no** official MCP or Remote API.
This repo talks to whichever backend is actually present:

| Priority | Backend | Default |
|---|---|---|
| 1 | Native Orca MCP HTTP (`POST /mcp`) | `http://127.0.0.1:13619` |
| 2 | MaxEllis Orca Remote API + this bridge | `http://127.0.0.1:13130` |
| 3 | CLI MCP (this repo) against Orca **or** Flash Studio binary | local `python3 mcp-server/orca_cli_mcp.py` |

Stock Flash Studio almost always lands on **3**.

## Daily (Mac)

```bash
# once
brew install cloudflare/cloudflare/cloudflared
bash installers/install-grok-orca.sh

# each session: slicer running first
start-orca-grok-stack
# paste GROK_CONNECTOR_URL into grok.com/connectors → Custom
stop-orca-grok-stack
```

Hostname changes every `trycloudflare` start.

## Grok Build (no tunnel)

```bash
grok mcp add --transport http orcaslicer http://127.0.0.1:18783/mcp
```

Or stdio MaxEllis server if you run the patched slicer:

```bash
grok mcp add orcaslicer -e ORCA_API_TOKEN=TOKEN -- uvx orcaslicer-mcp
```

Docs: [docs/INSTALL.md](docs/INSTALL.md) · [docs/BACKENDS.md](docs/BACKENDS.md)
