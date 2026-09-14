# Backends

## 1. Native in-slicer MCP (best for grok.com)

Orca discussion [#12668](https://github.com/OrcaSlicer/OrcaSlicer/discussions/12668) / kosmo Windows build.

- Transport: Streamable HTTP `POST /mcp`
- Typical port: `13619`
- This repo only Host-rewrites + tunnels (same as Fusion bridge).

Flash Studio 1.7.x does **not** ship this.
Native mode does **not** expose `ad5x_*` tools.

## 2. MaxEllis Remote API + `uvx orcaslicer-mcp`

- Slicer API: `http://127.0.0.1:13130` (token in Preferences → Remote API)
- MCP process is **stdio**, not HTTP.
- Use **Grok Build** (`grok mcp add ... uvx orcaslicer-mcp`), not grok.com Custom, unless you add a separate HTTP wrapper.
- This stack will proxy `13130` only if that port already speaks MCP HTTP. Stock MaxEllis API is REST, not MCP.

## 3. CLI MCP in this repo (Flash Studio fallback)

`mcp-server/orca_cli_mcp.py` exposes a small Streamable HTTP MCP:

- `slicer_health`
- `detect_slicer`
- `list_profiles`
- `slice_model`
- plus `ad5x_*` when `mcp-server/ad5x_lan.py` is present

It shells the binary with Orca-style `--slice` flags. If Flash Studio dropped CLI, the tool returns the exact command + stderr so you can switch to an Orca build.

## Flashforge AD5X LAN send

Enabled on remote + CLI MCP modes. Tools `ad5x_*` call printer HTTP `:8898` on the LAN (serial + Device ID). Not tunneled.
See [AD5X-LAN.md](AD5X-LAN.md).
