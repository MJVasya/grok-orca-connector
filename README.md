# Grok Orca stack

Sibling of [grok-fusion-connector](https://github.com/MJVasya/grok-fusion-connector).
Local MCP → Host-rewrite bridge `:18783` → Cloudflare quick tunnel → `GROK_CONNECTOR_URL` for [grok.com/connectors](https://grok.com/connectors) Custom.

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

start-orca-grok-stack
```

Need: `Mode: MaxEllis Remote API HTTP-MCP wrapper`  
(401 on `:13130` is API up. Empty token / stock Orca without Remote API → CLI mode, no live GUI.)

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
| 18785 | Remote-API HTTP-MCP wrapper |
| 18782 | Fusion — not this repo |

## Live GUI tools (wrapper mode)

`orca_health` `orca_status` `orca_get_config` `orca_set_config` `orca_load_model` `orca_arrange` `orca_slice` `orca_list_presets` `orca_select_preset` `orca_api`

Docs: [docs/REMOTE-API.md](docs/REMOTE-API.md) · [docs/BACKENDS.md](docs/BACKENDS.md)
