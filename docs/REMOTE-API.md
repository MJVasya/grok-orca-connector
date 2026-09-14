# MaxEllis Remote API → grok.com

`mcp-server/orca_remote_mcp.py` is Streamable HTTP MCP. It calls the slicer REST API so the **open GUI** updates.

## Enable

1. MaxEllis OrcaSlicer MCP app running.
2. Preferences → Remote API → enable → copy token.
3. Save token (do not commit it):

```bash
mkdir -p ~/.grok/orca-stack
echo 'PASTE_TOKEN' > ~/.grok/orca-stack/token
chmod 600 ~/.grok/orca-stack/token
```

4. `git pull` this repo, then `start-orca-grok-stack`.
5. Expect `Mode: MaxEllis Remote API HTTP-MCP wrapper`.
6. Paste `GROK_CONNECTOR_URL` into grok.com Custom (replace old URL; hostname changes each start).

## Tools Grok should call

`orca_health` → `orca_load_model` `{path}` → `orca_arrange` → `orca_set_config` → `orca_slice` → `orca_status`

`orca_api` is an escape hatch if MaxEllis renamed a path.

Auth headers sent: `Authorization: Bearer`, `X-API-Token`, `X-Orca-Token`.

Convenience tools try several `/api/v1/...` paths. First 2xx wins. If all 404, use `orca_api` after checking slicer logs / their docs.
