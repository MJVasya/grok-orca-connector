# Grok Orca stack

> **Wrap of [MaxEllis/orcaslicer-mcp](https://github.com/MaxEllis/orcaslicer-mcp) + MaxEllis Orca Remote API** — not a stdio drop-in.
> **What is different:** this repo exposes the slicer as **streamable HTTP MCP** and publishes it through a **Cloudflare quick tunnel** so **[grok.com Custom](https://grok.com/connectors)** (browser, no stdio) can call tools.
> Upstream `uvx orcaslicer-mcp` is local Claude Desktop only. Full delta: **[FORK.md](FORK.md)**.

Sibling of [grok-fusion-connector](https://github.com/MJVasya/grok-fusion-connector).

```
Grok.com  ==HTTPS==>  https://xxxx.trycloudflare.com/mcp
                         cloudflared
                            :18783 bridge (Host rewrite)
                            :18785 HTTP-MCP wrapper  <-- streamable HTTP
                            :13130 MaxEllis Remote API
AD5X stays local :8898 (not tunneled)
```

Fusion stays on `:18782`. This stack does not stop Fusion.

## New install

```bash
# Orca: MaxEllis MCP build + Preferences → Remote API → Enable → copy token
brew install cloudflare/cloudflare/cloudflared   # if needed

git clone https://github.com/MJVasya/grok-orca-connector.git
cd grok-orca-connector
bash installers/install-grok-orca.sh

mkdir -p ~/.grok/orca-stack
echo 'TOKEN_FROM_PREFERENCES' > ~/.grok/orca-stack/token
chmod 600 ~/.grok/orca-stack/token

# AD5X LAN (optional)
# {"ip":"192.168.x.x","serial":"SN...","checkCode":"DEVICE_ID","httpPort":8898}
# chmod 600 ~/.grok/orca-stack/ad5x.json

start-orca-grok-stack
```

Need: `Mode: MaxEllis Remote API HTTP-MCP wrapper` or CLI mode for `ad5x_*`.
(401 on `:13130` is API up. Empty token / stock Orca without Remote API → CLI mode, no live GUI.)
Native in-slicer `/mcp` does not include AD5X tools.

## Daily

Orca MCP app open, Remote API on → `start-orca-grok-stack` → paste URL into grok.com Custom.  
Done with this chat → `stop-orca-grok-stack`.  
No reinstall each session.  
Grok Build + `uvx orcaslicer-mcp` still needs no stack.

Prints `GROK_CONNECTOR_URL=https://….trycloudflare.com/mcp`. Hostname changes every start — update Custom.

## Kill

```bash
stop-orca-grok-stack
lsof -nP -iTCP:18783 -sTCP:LISTEN
```

Success is only:

```text
orca grok stack stopped
```

A WARN line appears **only if** `:18783` is still up. Fusion `cloudflared … :18782` is ignored.

Manual:

```bash
kill "$(cat ~/.grok/orca-stack/bridge.pid)"
kill "$(cat ~/.grok/orca-stack/remote.pid)"
kill "$(cat ~/.grok/orca-stack/cloudflared.pid)"
pkill -f 'cloudflared.*tunnel.*:18783'
```

Do **not** `pkill cloudflared` if Fusion is running.

## Update

```bash
stop-orca-grok-stack
cd ~/grok-orca-connector
git checkout -- installers/start-orca-grok-stack.sh installers/stop-orca-grok-stack.sh
git pull
bash installers/install-grok-orca.sh
start-orca-grok-stack
```

Local edits on those scripts block `git pull`. Quick-tunnel host changes — update the Custom connector URL.

## Remove

```bash
stop-orca-grok-stack
rm -f ~/.grok/bin/start-orca-grok-stack ~/.grok/bin/stop-orca-grok-stack
rm -rf ~/.grok/orca-stack ~/grok-orca-connector
```

Leave `~/.grok/fusion-stack` and Fusion brew formulas alone.

## Ports

| Port | Role |
|---|---|
| 13130 | MaxEllis Orca Remote API |
| 13619 | Native in-app `/mcp` (rare on Mac) |
| 18783 | Orca bridge (tunneled) |
| 18784 | CLI MCP fallback |
| 18785 | Remote-API **HTTP-MCP wrapper** (streamable HTTP) |
| 8898 | AD5X LAN HTTP (printer, not tunneled) |
| 18782 | Fusion — not this repo |

## Live GUI tools (wrapper mode)

`orca_health` `orca_status` `orca_get_config` `orca_set_config` `orca_load_model` `orca_arrange` `orca_slice` `orca_list_presets` `orca_select_preset` `orca_api`

AD5X LAN (same URL, printer stays local): `ad5x_discover` `ad5x_configure` `ad5x_health` `ad5x_detail` `ad5x_files` `ad5x_upload` `ad5x_print` `ad5x_job` `ad5x_control`

Docs: [FORK.md](FORK.md) · [docs/REMOTE-API.md](docs/REMOTE-API.md) · [docs/BACKENDS.md](docs/BACKENDS.md) · [docs/AD5X-LAN.md](docs/AD5X-LAN.md)
