# Install / daily (short)

Same shape as Fusion. Clone is the install path until a `mjvasya/grok` formula exists.

```bash
# Orca: Preferences → Remote API → token → ~/.grok/orca-stack/token
brew install cloudflare/cloudflare/cloudflared   # if needed
git clone https://github.com/MJVasya/grok-orca-connector.git
cd grok-orca-connector
bash installers/install-grok-orca.sh
start-orca-grok-stack
```

Daily: Orca Remote API on → `start-orca-grok-stack` → paste URL.  
If using Custom → `stop-orca-grok-stack`.  
No reinstall each session.  
Grok Build / `uvx orcaslicer-mcp` still needs no stack.

```bash
stop-orca-grok-stack
lsof -nP -iTCP:18783 -sTCP:LISTEN
```
