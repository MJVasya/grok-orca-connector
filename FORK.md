# Fork / wrap notes vs MaxEllis Orca MCP

This repo is **not** a line-for-line fork of [MaxEllis/orcaslicer-mcp](https://github.com/MaxEllis/orcaslicer-mcp).
It is a **runtime wrap** of the MaxEllis **OrcaSlicer MCP build** (Remote API on `:13130`) so a **web** MCP client can use it.

Upstream server: `uvx orcaslicer-mcp` — local **stdio** for Claude Desktop / local agents.
This stack: **streamable HTTP MCP** + host-rewrite bridge + Cloudflare quick tunnel → Grok.com Custom.

## The difference that matters: HTTP streaming for grok.com

Grok.com / SuperGrok Custom connectors only speak **MCP over HTTP** (JSON-RPC 2024-11-05, streamable HTTP). They **cannot** attach to a Mac stdio process and they **cannot** reach `127.0.0.1`.

```
Grok.com Custom  --HTTPS-->  trycloudflare.com/mcp
                                |
                         cloudflared quick tunnel
                                |
                    localhost:18783  host-rewrite bridge
                                |
                    localhost:18785  HTTP-MCP wrapper  (streamable HTTP)
                                |
                    localhost:13130  MaxEllis Orca Remote API (token)
```

| Layer | What it is |
|---|---|
| MaxEllis Orca app | GUI + token API on `:13130` (localhost) |
| `orca_remote_mcp.py` | Wraps that API as **streamable HTTP MCP** (`:18785`) |
| `bridge` | Rewrites `Host` so the tunnel origin looks local |
| `cloudflared tunnel --url http://127.0.0.1:18783` | Public `https://….trycloudflare.com/mcp` |
| Grok Custom | Paste `GROK_CONNECTOR_URL` each start |

**Improvement vs stock MaxEllis `uvx`:** same slicer tools, but usable from a **browser-hosted** assistant. No Claude Desktop required.

**Cost:** the hostname is public while the stack runs. `stop-orca-grok-stack` when idle. Token stays on disk (`~/.grok/orca-stack/token`, mode 600). AD5X creds never go through the tunnel — printer stays on LAN `:8898`.

## Other deltas

| Area | MaxEllis `orcaslicer-mcp` | This wrap |
|---|---|---|
| Transport | stdio | **Streamable HTTP MCP** |
| Client | Claude Desktop / local | **grok.com Custom** |
| Reachability | same machine | Cloudflare quick tunnel |
| Printer send | not in scope | Flashforge AD5X LAN `ad5x_*` |
| Fusion | n/a | Sibling stack on `:18782` left running |

## Not claimed as improvements

- Not a replacement for official SoftFever Orca.
- Device tab webview can stay blank; send uses Flashforge LAN or `ad5x_upload`.
- No Flashforge cloud/WAN API.

## Sync

Upstream MCP Python package stays `uvx orcaslicer-mcp`.
This repo tracks wrapper + bridge + AD5X client only.
