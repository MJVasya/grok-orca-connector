# AD5X LAN (grok-orca stack)

Printer stays on **LAN only**. Grok talks to the local MCP; MCP talks to `http://AD5X:8898`. Do not Cloudflare-tunnel the printer.

## Printer

1. Same Wi-Fi/subnet as the Mac running the stack.
2. Settings → Network → **LAN Only** ON.
3. Copy **Device ID** (checkCode) and serial from the printer screen / about page.
4. Confirm `:8898` answers (401/JSON is fine; connection refused is not).

## Config

```bash
mkdir -p ~/.grok/orca-stack
cat > ~/.grok/orca-stack/ad5x.json <<'EOF'
{
  "ip": "192.168.1.50",
  "serial": "SNADVA5XXXXX",
  "checkCode": "DEVICE_ID_FROM_SCREEN",
  "httpPort": 8898
}
EOF
chmod 600 ~/.grok/orca-stack/ad5x.json
```

Or from Grok after stack start: `ad5x_discover` then `ad5x_configure`.

## Tools (same MCP URL as slicer)

`ad5x_discover` `ad5x_configure` `ad5x_health` `ad5x_detail` `ad5x_files` `ad5x_upload` `ad5x_print` `ad5x_job` `ad5x_control`

Typical: slice via Orca tools → `ad5x_upload {path, printNow:false}` → `ad5x_print` if needed.

IFS multi-color: set `useMatlStation: true`, `gcodeToolCnt`, `materialMappings` `[{toolId, slotId, materialName, toolMaterialColor, slotMaterialColor}]`.

## Errors

| code | meaning |
|---|---|
| -2 | LAN mode off |
| 2 | printer busy |
| unreachable | wrong IP / firewall / not on LAN |

API ref: [Parallel-7 AD5X wiki](https://github.com/Parallel-7/flashforge-api-docs/wiki/AD5X-IFS-Material-Station)
