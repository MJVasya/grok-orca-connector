#!/usr/bin/env python3
"""AD5X LAN client: UDP discover + HTTP :8898 (serialNumber + checkCode).

Printer stays on the local network. Do not tunnel this client.
Unofficial API: https://github.com/Parallel-7/flashforge-api-docs/wiki
"""
from __future__ import annotations

import base64
import json
import os
import socket
import struct
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

CONFIG_PATH = Path(os.environ.get("AD5X_CONFIG", str(Path.home() / ".grok/orca-stack/ad5x.json")))
DEFAULT_HTTP_PORT = 8898
DISCOVER_TIMEOUT = 2.0


def load_config() -> dict:
    if not CONFIG_PATH.is_file():
        return {}
    try:
        data = json.loads(CONFIG_PATH.read_text())
    except json.JSONDecodeError:
        return {"error": f"invalid JSON: {CONFIG_PATH}"}
    return data if isinstance(data, dict) else {}


def save_config(data: dict) -> dict:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(data, indent=2) + "\n")
    os.chmod(CONFIG_PATH, 0o600)
    return {"ok": True, "path": str(CONFIG_PATH), "ip": data.get("ip"), "serial": data.get("serial")}


def _creds(cfg: dict | None = None) -> tuple[dict, str, str, str, int]:
    cfg = cfg or load_config()
    ip = str(cfg.get("ip") or os.environ.get("AD5X_IP") or "").strip()
    serial = str(cfg.get("serial") or os.environ.get("AD5X_SERIAL") or "").strip()
    code = str(cfg.get("checkCode") or os.environ.get("AD5X_CHECKCODE") or "").strip()
    port = int(cfg.get("httpPort") or os.environ.get("AD5X_HTTP_PORT") or DEFAULT_HTTP_PORT)
    return cfg, ip, serial, code, port


def _need(ip: str, serial: str, code: str) -> dict | None:
    missing = [n for n, v in (("ip", ip), ("serial", serial), ("checkCode", code)) if not v]
    if missing:
        return {
            "ok": False,
            "error": "missing " + ",".join(missing),
            "hint": f"write {CONFIG_PATH} with ip, serial, checkCode (Device ID on AD5X LAN Only screen)",
        }
    return None


def _auth_body(serial: str, code: str, extra: dict | None = None) -> bytes:
    body = {"serialNumber": serial, "checkCode": code}
    if extra:
        body.update(extra)
    return json.dumps(body).encode()


def http_json(method: str, ip: str, port: int, path: str, serial: str, code: str, extra: dict | None = None, timeout: int = 30) -> dict:
    url = f"http://{ip}:{port}{path}"
    req = Request(
        url,
        data=_auth_body(serial, code, extra) if method.upper() != "GET" else None,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        method=method.upper(),
    )
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            status = resp.status
    except HTTPError as e:
        raw = e.read() if e.fp else str(e).encode()
        status = e.code
    except URLError as e:
        return {"ok": False, "error": f"unreachable {url}: {e.reason}", "url": url}
    text = raw.decode("utf-8", "replace") if raw else ""
    try:
        parsed = json.loads(text) if text else None
    except json.JSONDecodeError:
        parsed = text[:4000]
    return {"ok": 200 <= status < 300, "status": status, "url": url, "body": parsed}


def upload_gcode(
    file_path: str,
    print_now: bool = False,
    leveling: bool = True,
    flow_cal: bool = False,
    use_ifs: bool = False,
    tool_count: int = 1,
    mappings: list | None = None,
    timeout: int = 300,
) -> dict:
    cfg, ip, serial, code, port = _creds()
    miss = _need(ip, serial, code)
    if miss:
        return miss
    src = Path(file_path).expanduser()
    if not src.is_file():
        return {"ok": False, "error": f"missing file: {src}"}
    data = src.read_bytes()
    boundary = "----GrokAd5xBoundary7f3a"
    filename = src.name
    parts = [
        f"--{boundary}\r\n".encode(),
        f'Content-Disposition: form-data; name="gcodeFile"; filename="{filename}"\r\n'.encode(),
        b"Content-Type: application/octet-stream\r\n\r\n",
        data,
        f"\r\n--{boundary}--\r\n".encode(),
    ]
    body = b"".join(parts)
    map_header = "[]"
    if mappings:
        map_header = base64.b64encode(json.dumps(mappings).encode()).decode()
    headers = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Content-Length": str(len(body)),
        "serialNumber": serial,
        "checkCode": code,
        "fileSize": str(len(data)),
        "printNow": "true" if print_now else "false",
        "levelingBeforePrint": "true" if leveling else "false",
        "flowCalibration": "true" if flow_cal else "false",
        "useMatlStation": "true" if use_ifs else "false",
        "gcodeToolCnt": str(int(tool_count)),
        "materialMappings": map_header,
    }
    url = f"http://{ip}:{port}/uploadGcode"
    req = Request(url, data=body, headers=headers, method="POST")
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            status = resp.status
    except HTTPError as e:
        raw = e.read() if e.fp else str(e).encode()
        status = e.code
    except URLError as e:
        return {"ok": False, "error": f"upload unreachable {url}: {e.reason}"}
    text = raw.decode("utf-8", "replace") if raw else ""
    try:
        parsed = json.loads(text) if text else None
    except json.JSONDecodeError:
        parsed = text[:4000]
    return {
        "ok": 200 <= status < 300,
        "status": status,
        "file": str(src),
        "bytes": len(data),
        "printNow": print_now,
        "body": parsed,
    }


def _cstr(buf: bytes) -> str:
    return buf.split(b"\x00", 1)[0].decode("utf-8", "replace").strip()


def parse_discovery(data: bytes, addr: str) -> dict | None:
    if len(data) < 0x92:
        return None
    name = _cstr(data[0x00:0x80])
    cmd_port = struct.unpack_from("<H", data, 0x84)[0] if len(data) >= 0x86 else 8899
    vid = struct.unpack_from("<H", data, 0x86)[0] if len(data) >= 0x88 else 0
    pid = struct.unpack_from("<H", data, 0x88)[0] if len(data) >= 0x8A else 0
    status = struct.unpack_from("<H", data, 0x8A)[0] if len(data) >= 0x8C else -1
    http_port = struct.unpack_from("<H", data, 0x8E)[0] if len(data) >= 0x90 else DEFAULT_HTTP_PORT
    serial = _cstr(data[0x92:0x92 + 128]) if len(data) >= 0x112 else ""
    return {
        "ip": addr,
        "name": name,
        "serial": serial,
        "vid": hex(vid),
        "pid": hex(pid),
        "status": status,
        "httpPort": http_port or DEFAULT_HTTP_PORT,
        "cmdPort": cmd_port,
        "packetBytes": len(data),
    }


def discover(timeout: float = DISCOVER_TIMEOUT) -> dict:
    found: dict[str, dict] = {}
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.settimeout(timeout)
    try:
        sock.bind(("", 0))
        try:
            sock.sendto(b"hello", ("255.255.255.255", 48899))
        except OSError:
            pass
        try:
            sock.sendto(b"hello", ("225.0.0.9", 19000))
        except OSError:
            pass
        sock.settimeout(0.4)
        import time
        end = time.time() + timeout
        while time.time() < end:
            try:
                payload, (ip, _port) = sock.recvfrom(512)
            except socket.timeout:
                continue
            parsed = parse_discovery(payload, ip)
            if parsed:
                found[ip] = parsed
    finally:
        sock.close()
    return {"ok": True, "count": len(found), "printers": list(found.values()), "note": "checkCode is not in discovery; copy Device ID from AD5X LAN Only screen"}


def health() -> dict:
    cfg, ip, serial, code, port = _creds()
    miss = _need(ip, serial, code)
    if miss:
        disc = discover()
        miss["discover"] = disc
        return miss
    probe = http_json("POST", ip, port, "/detail", serial, code)
    product = http_json("POST", ip, port, "/product", serial, code)
    check = http_json("POST", ip, port, "/checkCode", serial, code)
    body = probe.get("body")
    lan_err = False
    if isinstance(body, dict) and body.get("code") == -2:
        lan_err = True
    return {
        "ok": bool(probe.get("ok")) and not lan_err,
        "ip": ip,
        "serial": serial,
        "httpPort": port,
        "lanModeError": lan_err,
        "detail": probe,
        "product": product,
        "checkCode": check,
    }


def detail() -> dict:
    cfg, ip, serial, code, port = _creds()
    miss = _need(ip, serial, code)
    return miss or http_json("POST", ip, port, "/detail", serial, code)


def files() -> dict:
    cfg, ip, serial, code, port = _creds()
    miss = _need(ip, serial, code)
    return miss or http_json("POST", ip, port, "/gcodeList", serial, code)


def print_file(file_name: str, leveling: bool = True, flow_cal: bool = False, use_ifs: bool = False, tool_count: int = 1, mappings: list | None = None) -> dict:
    cfg, ip, serial, code, port = _creds()
    miss = _need(ip, serial, code)
    if miss:
        return miss
    extra = {
        "fileName": file_name,
        "levelingBeforePrint": leveling,
        "flowCalibration": flow_cal,
        "useMatlStation": use_ifs,
        "gcodeToolCnt": int(tool_count),
    }
    if mappings:
        extra["materialMappings"] = mappings
    return http_json("POST", ip, port, "/printGcode", serial, code, extra)


def job(action: str, job_id: str = "") -> dict:
    cfg, ip, serial, code, port = _creds()
    miss = _need(ip, serial, code)
    if miss:
        return miss
    action = (action or "").lower()
    if action not in ("pause", "resume", "stop", "cancel"):
        return {"ok": False, "error": "action must be pause|resume|stop"}
    if action == "cancel":
        action = "stop"
    extra = {"payload": {"cmd": "jobCtl_cmd", "args": {"jobID": job_id, "action": action}}}
    return http_json("POST", ip, port, "/control", serial, code, extra)


def control(cmd: str, args: dict | None = None) -> dict:
    cfg, ip, serial, code, port = _creds()
    miss = _need(ip, serial, code)
    if miss:
        return miss
    extra = {"payload": {"cmd": cmd, "args": args or {}}}
    return http_json("POST", ip, port, "/control", serial, code, extra)


def configure(ip: str, serial: str, check_code: str, http_port: int = DEFAULT_HTTP_PORT) -> dict:
    data = {"ip": ip.strip(), "serial": serial.strip(), "checkCode": check_code.strip(), "httpPort": int(http_port)}
    saved = save_config(data)
    saved["probe"] = health()
    return saved


AD5X_TOOLS = [
    {"name": "ad5x_discover", "description": "UDP-discover Flashforge printers on LAN (AD5X/5M). Does not return checkCode.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "ad5x_configure", "description": "Save AD5X LAN creds to ~/.grok/orca-stack/ad5x.json and probe /detail.", "inputSchema": {"type": "object", "properties": {"ip": {"type": "string"}, "serial": {"type": "string"}, "checkCode": {"type": "string", "description": "Device ID from printer LAN Only screen"}, "httpPort": {"type": "integer", "default": 8898}}, "required": ["ip", "serial", "checkCode"]}},
    {"name": "ad5x_health", "description": "Probe AD5X HTTP :8898 /detail /product. Requires ad5x.json.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "ad5x_detail", "description": "Live AD5X status including IFS material station if present.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "ad5x_files", "description": "List gcode files stored on the AD5X.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "ad5x_upload", "description": "Upload a local .gcode/.3mf to AD5X over LAN. Optionally start print.", "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}, "printNow": {"type": "boolean", "default": False}, "leveling": {"type": "boolean", "default": True}, "flowCalibration": {"type": "boolean", "default": False}, "useMatlStation": {"type": "boolean", "default": False}, "gcodeToolCnt": {"type": "integer", "default": 1}, "materialMappings": {"type": "array", "items": {"type": "object"}}}, "required": ["path"]}},
    {"name": "ad5x_print", "description": "Start a file already on the printer (/printGcode).", "inputSchema": {"type": "object", "properties": {"fileName": {"type": "string"}, "leveling": {"type": "boolean", "default": True}, "flowCalibration": {"type": "boolean", "default": False}, "useMatlStation": {"type": "boolean", "default": False}, "gcodeToolCnt": {"type": "integer", "default": 1}, "materialMappings": {"type": "array", "items": {"type": "object"}}}, "required": ["fileName"]}},
    {"name": "ad5x_job", "description": "Pause, resume, or stop the current AD5X job.", "inputSchema": {"type": "object", "properties": {"action": {"type": "string", "description": "pause|resume|stop"}}, "required": ["action"]}},
    {"name": "ad5x_control", "description": "Raw AD5X /control payload cmd + args.", "inputSchema": {"type": "object", "properties": {"cmd": {"type": "string"}, "args": {"type": "object"}}, "required": ["cmd"]}},
]


def call_ad5x(name: str, args: dict):
    if name == "ad5x_discover":
        return discover()
    if name == "ad5x_configure":
        return configure(args.get("ip", ""), args.get("serial", ""), args.get("checkCode", ""), args.get("httpPort") or DEFAULT_HTTP_PORT)
    if name == "ad5x_health":
        return health()
    if name == "ad5x_detail":
        return detail()
    if name == "ad5x_files":
        return files()
    if name == "ad5x_upload":
        return upload_gcode(args.get("path", ""), bool(args.get("printNow", False)), args.get("leveling", True), bool(args.get("flowCalibration", False)), bool(args.get("useMatlStation", False)), int(args.get("gcodeToolCnt") or 1), args.get("materialMappings"))
    if name == "ad5x_print":
        return print_file(args.get("fileName", ""), args.get("leveling", True), bool(args.get("flowCalibration", False)), bool(args.get("useMatlStation", False)), int(args.get("gcodeToolCnt") or 1), args.get("materialMappings"))
    if name == "ad5x_job":
        return job(args.get("action", ""))
    if name == "ad5x_control":
        return control(args.get("cmd", ""), args.get("args") or {})
    return None
