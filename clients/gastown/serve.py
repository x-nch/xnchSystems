#!/usr/bin/env python3
"""Gas Town HTTP bridge.

Implements the ``GastownClient`` contract (see ``xnch_mcp/gastown.py``):

- POST /api/workstreams  {title, goal, workspace_hint?, agent_hint?} -> {id, state}
- GET  /api/workstreams                -> {workstreams: [{id, state, ...}]}
- GET  /api/workstreams/{id}           -> {id, state, ...}

Authentication: Bearer token must match ``XNCH_GASTOWN_TOKEN`` in
``~/.xnch/gastown.env`` (which must equal ``XNCH_MCP_HTTP_TOKEN`` on the
xnch gateway).

State model: workstreams move through ``queued`` -> ``running`` ->
``completed`` | ``failed``. Spawn provisions a workspace under
``~/xnch-workstreams`` and, when a Gas Town HQ is present, dispatches via
``gt sling`` (auto-creating a bead + convoy). State is refreshed by a
background polling thread that reads ``gt``/``bd`` output.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import subprocess
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOME = Path.home()
WORKSPACE = HOME / "xnch-workstreams"
REGISTRY = WORKSPACE / ".workstreams.json"
ENV_FILE = HOME / ".xnch" / "gastown.env"
PORT = int(os.environ.get("GASTOWN_PORT", "7474"))
BIND = os.environ.get("GASTOWN_BIND", "127.0.0.1")
POLL_INTERVAL = float(os.environ.get("GASTOWN_POLL", "15"))

_GT = os.environ.get("GASTOWN_GT", "gt")
_BD = os.environ.get("GASTOWN_BD", "bd")

_lock = threading.Lock()
_state = {"workstreams": {}}


def _load_registry() -> dict:
    with _lock:
        if REGISTRY.exists():
            try:
                return json.loads(REGISTRY.read_text())
            except Exception:
                return {}
        return {}


def _save_registry(data: dict) -> None:
    with _lock:
        REGISTRY.parent.mkdir(parents=True, exist_ok=True)
        REGISTRY.write_text(json.dumps(data, indent=2))

def _token() -> str | None:
    if not ENV_FILE.exists():
        return None
    for line in ENV_FILE.read_text().splitlines():
        if line.startswith("XNCH_GASTOWN_TOKEN="):
            return line.split("=", 1)[1].strip()
    return None


def _gt_exists() -> bool:
    try:
        r = subprocess.run(
            [_GT, "status"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
        return r.returncode == 0
    except Exception:
        return False


def _run(cmd: list[str], timeout: int = 30) -> tuple[int, str, str]:
    try:
        r = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            cwd=str(WORKSPACE),
        )
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "timeout"
    except FileNotFoundError:
        return -1, "", f"{cmd[0]} not found"


def _try_dispatch(ws: dict) -> None:
    if not _gt_exists():
        return
    title = ws.get("title", "workstream")
    goal = ws.get("goal", "")

    rc, out, err = _run([_BD, "create", title, "--title", title,
                         "--description", goal[:500] if goal else ""])
    if rc != 0:
        ws["dispatch_error"] = err or out
        return
    try:
        payload = json.loads(out) if out.strip().startswith("{") else {}
    except json.JSONDecodeError:
        payload = {}
    bead_id = payload.get("id") or _parse_bead_id(out) or _slug_id(title)
    ws["bead_id"] = bead_id

    rc, out, err = _run([_GT, "convoy", "create", title, bead_id, "--owned",
                         "--merge=local"])
    if rc == 0:
        ws["convoy"] = _parse_convoy_id(out) or title

    rc, out, err = _run([_GT, "sling", bead_id, "mayor", "--args", goal[:400] if goal else title])
    if rc == 0:
        ws["state"] = "running"
    else:
        ws["dispatch_error"] = err or out


def _parse_bead_id(text: str) -> str | None:
    for line in text.splitlines():
        if "Created issue:" in line or "created issue:" in line:
            for tok in line.split(":")[-1].split():
                if tok.startswith(("gt-", "bd-", "ws-", "hq-", "xnch-workstreams-")):
                    return tok
    for line in text.splitlines():
        for tok in line.split():
            if tok.startswith(("gt-", "bd-", "ws-", "hq-", "xnch-workstreams-")):
                return tok
    return None


def _parse_convoy_id(text: str) -> str | None:
    for line in text.splitlines():
        if "convoy" in line.lower():
            for tok in line.split():
                if tok.startswith("c-") and len(tok) >= 4:
                    return tok
    return None


def _slug_id(title: str) -> str:
    return "ws-" + hashlib.sha256(title.encode()).hexdigest()[:8]


def _poll_states() -> None:
    while True:
        try:
            data = _load_registry()
            changed = False
            for ws_id, ws in data.get("workstreams", {}).items():
                if ws.get("state") in ("completed", "failed"):
                    continue
                if ws.get("bead_id"):
                    rc, out, _ = _run([_BD, "show", ws["bead_id"]])
                    if rc == 0:
                        lower = out.lower()
                        if "closed" in lower or "done" in lower or "completed" in lower:
                            if ws["state"] != "completed":
                                ws["state"] = "completed"
                                changed = True
                        elif "failed" in lower or "error" in lower:
                            if ws["state"] != "failed":
                                ws["state"] = "failed"
                                changed = True
                        elif ws["state"] not in ("queued", "running"):
                            ws["state"] = "running"
                            changed = True
                    else:
                        if ws.get("dispatch_error") and ws["state"] == "queued":
                            ws["state"] = "failed"
                            changed = True
            if changed:
                _save_registry(data)
        except Exception:
            pass
        time.sleep(POLL_INTERVAL)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _send(self, code: int, body: dict) -> None:
        payload = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _auth_ok(self) -> bool:
        header = self.headers.get("Authorization", "")
        expected = _token()
        if not expected or not header.startswith("Bearer "):
            return False
        return header[len("Bearer "):].strip() == expected

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b""
        try:
            return json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return {}

    def do_POST(self):
        if self.path == "/api/workstreams":
            if not self._auth_ok():
                self._send(401, {"error": "unauthorized"})
                return
            body = self._read_body()
            title = str(body.get("title", "")).strip()
            goal = str(body.get("goal", "")).strip()
            if not title or not goal:
                self._send(400, {"error": "title and goal are required"})
                return
            ws_id = "ws-" + uuid.uuid4().hex[:8]
            workspace = WORKSPACE / ws_id
            workspace.mkdir(parents=True, exist_ok=True)
            ws = {
                "id": ws_id,
                "state": "queued",
                "title": title,
                "goal": goal,
                "workspace_hint": body.get("workspace_hint"),
                "agent_hint": body.get("agent_hint"),
                "workspace": str(workspace),
                "created_at": datetime.datetime.now().isoformat(),
            }
            data = _load_registry()
            ws_list = data.setdefault("workstreams", {})
            ws_list[ws_id] = ws
            _save_registry(data)
            try:
                _try_dispatch(ws)
                data = _load_registry()
                data.setdefault("workstreams", {})[ws_id].update(ws)
                _save_registry(data)
            except Exception as exc:
                data = _load_registry()
                data.setdefault("workstreams", {})[ws_id]["dispatch_error"] = str(exc)
                _save_registry(data)
            self._send(201, {"id": ws_id, "state": ws["state"]})
        else:
            self._send(404, {"error": "not found"})

    def do_GET(self):
        if self.path == "/api/workstreams":
            if not self._auth_ok():
                self._send(401, {"error": "unauthorized"})
                return
            data = _load_registry()
            out = []
            for ws_id, ws in data.get("workstreams", {}).items():
                out.append({
                    "id": ws.get("id", ws_id),
                    "state": ws.get("state", "queued"),
                    "title": ws.get("title"),
                    "goal": ws.get("goal"),
                    "workspace_hint": ws.get("workspace_hint"),
                    "agent_hint": ws.get("agent_hint"),
                    "workspace": ws.get("workspace"),
                    "created_at": ws.get("created_at"),
                    "bead_id": ws.get("bead_id"),
                    "convoy": ws.get("convoy"),
                    "dispatch_error": ws.get("dispatch_error"),
                })
            self._send(200, {"workstreams": out})
        elif self.path.startswith("/api/workstreams/"):
            if not self._auth_ok():
                self._send(401, {"error": "unauthorized"})
                return
            ws_id = self.path[len("/api/workstreams/"):]
            data = _load_registry()
            ws = data.get("workstreams", {}).get(ws_id)
            if not ws:
                self._send(404, {"error": "not found"})
                return
            self._send(200, {
                "id": ws.get("id", ws_id),
                "state": ws.get("state", "queued"),
                "title": ws.get("title"),
                "goal": ws.get("goal"),
                "workspace_hint": ws.get("workspace_hint"),
                "agent_hint": ws.get("agent_hint"),
                "workspace": ws.get("workspace"),
                "created_at": ws.get("created_at"),
                "bead_id": ws.get("bead_id"),
                "convoy": ws.get("convoy"),
                "dispatch_error": ws.get("dispatch_error"),
            })
        else:
            self._send(404, {"error": "not found"})

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - - [%s] %s\n" % (
            self.address_string(),
            self.log_date_time_string(),
            fmt % args,
        ))


def main() -> None:
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((BIND, PORT), Handler)
    threading.Thread(target=_poll_states, daemon=True).start()
    print(f"Gas Town bridge listening on {BIND}:{PORT} (token set={bool(_token())})", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
