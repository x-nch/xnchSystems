"""Local WebSocket (:9001) + HTTP (:9002) bridge between daemon and UI.

The Tauri/Svelte UI connects to the WebSocket. The daemon pushes status,
health, and voice results with broadcast(); the UI can also send JSON
commands (e.g. {"type": "arm"}) which are dispatched to on_command.
"""

from __future__ import annotations

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable

import websockets

_clients: set = set()
_bridge_loop: asyncio.AbstractEventLoop | None = None
_on_command: Callable[[dict], None] | None = None
_http_server: ThreadingHTTPServer | None = None

_MOBILE_PAGE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>XNCH CC</title></head>
<body style="background:#000;color:#fff;font-family:sans-serif;padding:24px">
<div id="a">Waiting...</div>
<script>
var w=new WebSocket('ws://'+location.hostname+':9001');
w.onmessage=function(e){var m=JSON.parse(e.data);var el=document.getElementById('a');
 if(m.type==='voice_result')el.textContent=(m.transcript?('Q: '+m.transcript+'\\n'):'')+m.response;
 else if(m.type==='status')el.textContent=m.text};
</script></body></html>"""


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(_MOBILE_PAGE.encode())
        except ConnectionResetError:
            pass

    def log_message(self, *args) -> None:  # silence
        pass


async def _handler(ws) -> None:
    global _on_command
    _clients.add(ws)
    try:
        async for raw in ws:
            if _on_command is None:
                continue
            try:
                _on_command(json.loads(raw))
            except json.JSONDecodeError:
                pass
    except websockets.ConnectionClosed:
        pass
    finally:
        _clients.discard(ws)


async def _serve() -> None:
    async with websockets.serve(_handler, _HOST, _WS_PORT):
        await asyncio.Future()


def _run_ws() -> None:
    try:
        _bridge_loop.run_until_complete(_serve())
    except (RuntimeError, asyncio.CancelledError):
        pass  # loop stopped or serve task cancelled during teardown


def start_bridge(
    on_command: Callable[[dict], None] | None = None,
    *,
    host: str = "127.0.0.1",
    ws_port: int = 9001,
    http_port: int = 9002,
) -> None:
    global _bridge_loop, _on_command, _HOST, _WS_PORT, _HTTP_PORT, _http_server
    _on_command = on_command
    _HOST = host
    _WS_PORT = ws_port
    _HTTP_PORT = http_port
    _http_server = ThreadingHTTPServer((host, http_port), _Handler)
    threading.Thread(target=_http_server.serve_forever, daemon=True).start()
    _bridge_loop = asyncio.new_event_loop()
    threading.Thread(target=_run_ws, daemon=True).start()


async def _send_all(payload: dict) -> None:
    if not _clients:
        return
    msg = json.dumps(payload)
    await asyncio.gather(*[c.send(msg) for c in _clients], return_exceptions=True)


def broadcast(payload: dict) -> None:
    loop = _bridge_loop
    if loop is None or not loop.is_running():
        return
    asyncio.run_coroutine_threadsafe(_send_all(payload), loop)
