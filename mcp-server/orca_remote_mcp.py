#!/usr/bin/env python3
"""Streamable HTTP MCP wrapping MaxEllis OrcaSlicer Remote API (REST :13130).

Grok.com -> tunnel -> this server /mcp -> Authorization token -> GUI API.
Changes land in the running Orca window.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pathlib import Path as _P
import sys as _sys
_sys.path.insert(0, str(_P(__file__).resolve().parent))
try:
    from ad5x_lan import AD5X_TOOLS, call_ad5x
except Exception:
    AD5X_TOOLS = []
    def call_ad5x(name, args):
        return None

SERVER_NAME = "grok-orca-remote"
SERVER_VERSION = "1.0.0"
PROTOCOL = "2024-11-05"
API = os.environ.get("ORCA_API_URL", "http://127.0.0.1:13130").rstrip("/")
TOKEN = os.environ.get("ORCA_API_TOKEN", "")


def api(method: str, path: str, body=None, timeout=180):
    if not path.startswith("/"):
        path = "/" + path
    url = API + path
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {TOKEN}",
        "X-API-Token": TOKEN,
        "X-Orca-Token": TOKEN,
    }
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    req = Request(url, data=data, headers=headers, method=method.upper())
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            code = resp.status
    except HTTPError as e:
        raw = e.read() if e.fp else str(e).encode()
        code = e.code
    except URLError as e:
        return {"ok": False, "error": f"unreachable {url}: {e.reason}", "url": url}
    text = raw.decode("utf-8", "replace") if raw else ""
    parsed = None
    try:
        parsed = json.loads(text) if text else None
    except json.JSONDecodeError:
        parsed = text[:8000]
    return {"ok": 200 <= code < 300, "status": code, "url": url, "method": method, "body": parsed}


def first_ok(tries):
    last = None
    for method, path, body in tries:
        last = api(method, path, body)
        if last.get("ok"):
            return last
    return last or {"ok": False, "error": "no attempts"}


TOOLS = [
    {
        "name": "orca_health",
        "description": "Ping MaxEllis Remote API and confirm token/GUI are up.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "orca_status",
        "description": "Read live slicer / plate / job status from the GUI API.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "orca_get_config",
        "description": "Read current print/filament/machine config from the open project.",
        "inputSchema": {"type": "object", "properties": {"keys": {"type": "string", "description": "optional comma-separated keys"}}},
    },
    {
        "name": "orca_set_config",
        "description": "Patch settings on the open project. Values appear in the GUI.",
        "inputSchema": {
            "type": "object",
            "properties": {"settings": {"type": "object"}},
            "required": ["settings"],
        },
    },
    {
        "name": "orca_load_model",
        "description": "Load an STL/3MF/STEP from a local path into the open plate (GUI updates).",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "orca_arrange",
        "description": "Auto-arrange and/or auto-orient objects on the plate.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "arrange": {"type": "boolean", "default": True},
                "orient": {"type": "boolean", "default": True},
            },
        },
    },
    {
        "name": "orca_slice",
        "description": "Slice the current plate in the GUI. Watch progress in Orca.",
        "inputSchema": {"type": "object", "properties": {"wait": {"type": "boolean", "default": True}}},
    },
    {
        "name": "orca_list_presets",
        "description": "List machine/process/filament presets visible to the GUI.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "orca_select_preset",
        "description": "Select a preset by name or id.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "type": {"type": "string", "description": "machine|process|filament"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "orca_api",
        "description": "Raw Remote API call when a convenience tool misses an endpoint. path like /api/v1/config",
        "inputSchema": {
            "type": "object",
            "properties": {
                "method": {"type": "string", "default": "GET"},
                "path": {"type": "string"},
                "body": {"type": "object"},
            },
            "required": ["path"],
        },
    },
] + AD5X_TOOLS


def call_tool(name: str, args: dict):
    ad = call_ad5x(name, args)
    if ad is not None:
        return ad
    if not TOKEN:
        return {"ok": False, "error": "ORCA_API_TOKEN empty. Preferences → Remote API."}
    if name == "orca_health":
        return {
            "token_set": bool(TOKEN),
            "api": API,
            "probe": first_ok(
                [
                    ("GET", "/api/v1/status", None),
                    ("GET", "/api/status", None),
                    ("GET", "/status", None),
                    ("GET", "/", None),
                ]
            ),
        }
    if name == "orca_status":
        return first_ok(
            [
                ("GET", "/api/v1/status", None),
                ("GET", "/api/v1/job", None),
                ("GET", "/api/v1/plate", None),
            ]
        )
    if name == "orca_get_config":
        keys = args.get("keys")
        path = "/api/v1/config"
        if keys:
            path += "?keys=" + str(keys)
        return first_ok([("GET", path, None), ("GET", "/api/v1/settings", None)])
    if name == "orca_set_config":
        settings = args.get("settings") or {}
        return first_ok(
            [
                ("PUT", "/api/v1/config", settings),
                ("PATCH", "/api/v1/config", settings),
                ("POST", "/api/v1/config", settings),
            ]
        )
    if name == "orca_load_model":
        p = args.get("path")
        body = {"path": p, "file": p, "filename": p}
        return first_ok(
            [
                ("POST", "/api/v1/models", body),
                ("POST", "/api/v1/model", body),
                ("POST", "/api/v1/load", body),
            ]
        )
    if name == "orca_arrange":
        body = {"arrange": args.get("arrange", True), "orient": args.get("orient", True)}
        return first_ok(
            [
                ("POST", "/api/v1/plate/arrange", body),
                ("POST", "/api/v1/arrange", body),
            ]
        )
    if name == "orca_slice":
        wait = args.get("wait", True)
        body = {"wait": wait}
        return first_ok(
            [
                ("POST", "/api/v1/slice", body),
                ("POST", "/api/v1/slice/wait" if wait else "/api/v1/slice", body),
            ]
        )
    if name == "orca_list_presets":
        return first_ok(
            [
                ("GET", "/api/v1/presets", None),
                ("GET", "/api/v1/profiles", None),
            ]
        )
    if name == "orca_select_preset":
        body = {"name": args.get("name"), "type": args.get("type")}
        return first_ok(
            [
                ("POST", "/api/v1/presets/select", body),
                ("PUT", "/api/v1/presets/select", body),
            ]
        )
    if name == "orca_api":
        return api(args.get("method") or "GET", args.get("path") or "/", args.get("body"))
    return {"error": f"unknown tool {name}"}


def rpc(msg: dict):
    mid = msg.get("id")
    method = msg.get("method")
    params = msg.get("params") or {}
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": mid,
            "result": {
                "protocolVersion": PROTOCOL,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        }
    if method == "notifications/initialized":
        return None
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": mid, "result": {}}
    if method == "tools/call":
        result = call_tool(params.get("name"), params.get("arguments") or {})
        return {
            "jsonrpc": "2.0",
            "id": mid,
            "result": {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]},
        }
    if mid is None:
        return None
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": str(method)}}


class Handler(BaseHTTPRequestHandler):
    server_version = "GrokOrcaRemoteMCP/1.0"

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _json(self, code, payload):
        raw = b"" if payload is None else json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        if payload is not None and self.command != "HEAD":
            self.wfile.write(raw)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self):
        self._json(200, {"name": SERVER_NAME, "version": SERVER_VERSION, "api": API, "token_set": bool(TOKEN)})

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b"{}"
        try:
            msg = json.loads(body.decode() or "{}")
        except json.JSONDecodeError:
            self._json(400, {"error": "invalid json"})
            return
        out = rpc(msg)
        if out is None:
            self.send_response(202)
            self.end_headers()
            return
        self._json(200, out)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--listen", default="127.0.0.1")
    p.add_argument("--port", type=int, default=18785)
    args = p.parse_args()
    print(f"Grok Orca Remote MCP  http://{args.listen}:{args.port}/mcp  ->  {API}", flush=True)
    if not TOKEN:
        print("WARN: ORCA_API_TOKEN empty", flush=True)
    ThreadingHTTPServer((args.listen, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
