#!/usr/bin/env python3
"""Minimal Streamable HTTP MCP for OrcaSlicer / Flash Studio CLI."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SERVER_NAME = "grok-orca-cli"
SERVER_VERSION = "1.0.0"
PROTOCOL = "2024-11-05"

CANDIDATE_BINS = [
    os.environ.get("ORCA_SLICER_BIN", ""),
    "/Applications/OrcaSlicer.app/Contents/MacOS/OrcaSlicer",
    "/Applications/Flash Studio.app/Contents/MacOS/Flash Studio",
    "/Applications/Flash Studio.app/Contents/MacOS/Orca-Flashforge",
    "/Applications/Orca-Flashforge.app/Contents/MacOS/Orca-Flashforge",
]

CANDIDATE_DATA = [
    os.environ.get("ORCA_SLICER_DATA", ""),
    str(Path.home() / "Library/Application Support/OrcaSlicer"),
    str(Path.home() / "Library/Application Support/Flash Studio"),
    str(Path.home() / "Library/Application Support/Orca-Flashforge"),
]


def first_existing_file(paths):
    for p in paths:
        if p and Path(p).is_file():
            return p
    which = shutil.which("orca-slicer") or shutil.which("OrcaSlicer")
    return which


def first_existing_dir(paths):
    for p in paths:
        if p and Path(p).is_dir():
            return p
    return None


def detect():
    return {
        "binary": first_existing_file(CANDIDATE_BINS),
        "data_dir": first_existing_dir(CANDIDATE_DATA),
    }


def list_profiles(data_dir: str | None):
    if not data_dir:
        return {"error": "no data dir", "profiles": []}
    root = Path(data_dir)
    hits = []
    for sub in ("user", "system", ""):
        base = root / sub if sub else root
        if not base.is_dir():
            continue
        for p in base.rglob("*.json"):
            rel = str(p.relative_to(root))
            if any(x in rel.lower() for x in ("filament", "process", "machine", "print")):
                hits.append(rel)
            if len(hits) >= 80:
                return {"data_dir": data_dir, "profiles": hits, "truncated": True}
    return {"data_dir": data_dir, "profiles": hits, "truncated": False}


def slice_model(file_path: str, output: str | None, extra: list[str] | None):
    det = detect()
    binary = det["binary"]
    if not binary:
        return {"ok": False, "error": "no slicer binary found", "detect": det}
    src = Path(file_path).expanduser()
    if not src.is_file():
        return {"ok": False, "error": f"missing model: {src}"}
    out = Path(output).expanduser() if output else src.with_suffix(".gcode")
    cmd = [binary, "--slice", "0", "--export-gcode", str(out), str(src)]
    if extra:
        cmd[1:1] = extra
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "slice timeout", "cmd": cmd}
    except FileNotFoundError as e:
        return {"ok": False, "error": str(e), "cmd": cmd}
    return {
        "ok": proc.returncode == 0,
        "cmd": cmd,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
        "output": str(out),
        "output_exists": out.is_file(),
    }


TOOLS = [
    {
        "name": "slicer_health",
        "description": "Ping this MCP server and report detected slicer paths.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "detect_slicer",
        "description": "Locate OrcaSlicer or Flash Studio binary and config dir.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "list_profiles",
        "description": "List machine/filament/process JSON presets under the slicer data dir.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "slice_model",
        "description": "Slice an STL/3MF via the slicer CLI. Flash Studio may reject Orca flags; stderr is returned.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string"},
                "output": {"type": "string"},
            },
            "required": ["file_path"],
        },
    },
]


def call_tool(name: str, args: dict):
    if name == "slicer_health":
        return {"server": SERVER_NAME, "version": SERVER_VERSION, **detect()}
    if name == "detect_slicer":
        return detect()
    if name == "list_profiles":
        return list_profiles(detect()["data_dir"])
    if name == "slice_model":
        return slice_model(args.get("file_path", ""), args.get("output"), None)
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
        name = params.get("name")
        arguments = params.get("arguments") or {}
        result = call_tool(name, arguments)
        text = json.dumps(result, indent=2)
        return {
            "jsonrpc": "2.0",
            "id": mid,
            "result": {"content": [{"type": "text", "text": text}]},
        }
    if mid is None:
        return None
    return {
        "jsonrpc": "2.0",
        "id": mid,
        "error": {"code": -32601, "message": f"method not found: {method}"},
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "GrokOrcaCliMCP/1.0"

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _json(self, code: int, payload):
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
        if self.path.rstrip("/") in ("", "/", "/mcp"):
            self._json(200, {"name": SERVER_NAME, "version": SERVER_VERSION, "transport": "streamable-http"})
            return
        self._json(404, {"error": "not found"})

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
    p.add_argument("--port", type=int, default=18784)
    args = p.parse_args()
    httpd = ThreadingHTTPServer((args.listen, args.port), Handler)
    print(f"Grok Orca CLI MCP  http://{args.listen}:{args.port}/mcp", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped", flush=True)


if __name__ == "__main__":
    main()
