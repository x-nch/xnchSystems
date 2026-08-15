# Mac Command Center Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build phase 1 of the Mac command center — a native Tauri app + Python capture daemon that gives the operator voice (push-to-talk to gate7) and cluster status on the Mac, thin-controller style (all compute on the cluster).

**Architecture:** A Python daemon on the Mac runs an always-on mic capture loop with WebRTC VAD. When armed (hotkey or in-app button), speech segments are POSTed to gate7 `xnch :8001` `POST /nexi/voice/chat`; the returned transcript + Nexi response + TTS audio are pushed to the UI over a local WebSocket. A Tauri 2 (Svelte) shell displays cluster health (xnch / nexi / media-gateway), the push-to-talk button, and the conversation. Nothing heavy runs on the Mac.

**Tech Stack:** Python 3.13 (sounddevice, webrtcvad, httpx, websockets, pynput, pyjwt, numpy), Tauri 2 + Svelte 5 + Vite 6, Rust 1.95.

**Spec:** `docs/superpowers/specs/2026-08-15-mac-command-center-design.md`

## Global Constraints

- Python 3.13+ (repo `.venv`), pytest runs in `asyncio_mode=auto` (sync tests fine).
- Mac is a thin controller: no STT/TTS/LLM/media on the Mac. All model compute stays on gate7 (`http://192.168.1.10:8001`) and node-b.
- Voice API is `POST /nexi/voice/chat` (multipart `audio` file + `session_id`/`actor_role`/`return_audio` form fields) — mirrors `cli/client.py:voice_chat`; do NOT add an Authorization header (the CLI doesn't, and it's the proven path).
- Config via `~/.xnch/xnch.env` style env vars (`XNCH_BASE_URL`, `XNCH_AUTH_SECRET`, `XNCH_ACTOR`, `NEXI_BASE_URL`, `MEDIA_GATEWAY_URL`, `XNCH_VOICE_*`).
- daemon modules are importable as `daemon.<module>` with `mac/` on `sys.path`.
- Do not modify `cli/`, `web/`, `xnch/`, `nexi/` code — the daemon is self-contained under `mac/`.
- No local inference, no mlx-whisper, no speechbrain in phase 1.

---

### Task 1: mac/ skeleton — requirements, daemon package, config

**Files:**
- Create: `mac/requirements.txt`
- Create: `mac/daemon/__init__.py`
- Create: `mac/daemon/config.py`
- Test: `mac/daemon/tests/conftest.py`, `mac/daemon/tests/test_config.py`

**Interfaces:**
- Produces: `daemon.config.DaemonConfig` (frozen dataclass) with classmethod `from_env()` and method `auth_header() -> str`; `DaemonConfig` fields: `base_url`, `auth_secret`, `auth_token`, `actor`, `nexi_url`, `media_url`, `sample_rate`, `input_device` (`int | str | None`), `output_device` (`int | str | None`), `ws_host`, `ws_port`, `http_port`.

- [ ] **Step 1: Write the failing test**

`mac/daemon/tests/conftest.py`:
```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
```

`mac/daemon/tests/test_config.py`:
```python
from daemon.config import DaemonConfig


def test_defaults(monkeypatch):
    for var in ("XNCH_BASE_URL", "XNCH_AUTH_SECRET", "XNCH_AUTH_TOKEN",
                "XNCH_ACTOR", "NEXI_BASE_URL", "MEDIA_GATEWAY_URL",
                "XNCH_VOICE_SAMPLE_RATE", "XNCH_VOICE_INPUT_DEVICE",
                "XNCH_VOICE_OUTPUT_DEVICE"):
        monkeypatch.delenv(var, raising=False)
    cfg = DaemonConfig.from_env()
    assert cfg.base_url == "http://192.168.1.10:8001"
    assert cfg.actor == "operator"
    assert cfg.nexi_url == "http://192.168.1.9:8001"
    assert cfg.media_url == "http://192.168.1.9:8090"
    assert cfg.sample_rate == 16000
    assert cfg.input_device is None
    assert cfg.output_device is None


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("XNCH_BASE_URL", "http://10.0.0.5:8001/")
    monkeypatch.setenv("XNCH_VOICE_INPUT_DEVICE", "2")
    monkeypatch.setenv("XNCH_VOICE_OUTPUT_DEVICE", "AirPods")
    cfg = DaemonConfig.from_env()
    assert cfg.base_url == "http://10.0.0.5:8001"
    assert cfg.input_device == 2
    assert cfg.output_device == "AirPods"


def test_auth_header_priority(monkeypatch):
    monkeypatch.setenv("XNCH_AUTH_TOKEN", "tok")
    monkeypatch.setenv("XNCH_AUTH_SECRET", "secret")
    assert DaemonConfig.from_env().auth_header() == "Bearer tok"
    monkeypatch.delenv("XNCH_AUTH_TOKEN", raising=False)
    header = DaemonConfig.from_env().auth_header()
    assert header.startswith("Bearer ")
    monkeypatch.delenv("XNCH_AUTH_SECRET", raising=False)
    assert DaemonConfig.from_env().auth_header() == "actor:operator"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd mac && .venv/bin/pytest daemon/tests/test_config.py -v` (from repo root: `uv run pytest mac/daemon/tests/test_config.py`)
Expected: FAIL — `ModuleNotFoundError: No module named 'daemon'`

- [ ] **Step 3: Write the implementation**

`mac/requirements.txt`:
```
httpx>=0.28
pyjwt>=2.8
sounddevice>=0.5
numpy>=1.26
webrtcvad>=0.0.3
pynput>=1.7.6
websockets>=12.0
```

`mac/daemon/__init__.py`:
```python
"""XNCH command center daemon — thin-client capture + voice on gate7."""
```

`mac/daemon/config.py`:
```python
"""Daemon configuration from environment variables."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass


def _device(raw: str) -> int | str | None:
    raw = raw.strip()
    if not raw:
        return None
    return int(raw) if raw.isdigit() else raw


@dataclass(frozen=True)
class DaemonConfig:
    base_url: str
    auth_secret: str
    auth_token: str
    actor: str
    nexi_url: str
    media_url: str
    sample_rate: int
    input_device: int | str | None
    output_device: int | str | None
    ws_host: str
    ws_port: int
    http_port: int

    @classmethod
    def from_env(cls) -> "DaemonConfig":
        return cls(
            base_url=os.environ.get("XNCH_BASE_URL", "http://192.168.1.10:8001").rstrip("/"),
            auth_secret=os.environ.get("XNCH_AUTH_SECRET", ""),
            auth_token=os.environ.get("XNCH_AUTH_TOKEN", ""),
            actor=os.environ.get("XNCH_ACTOR", "operator"),
            nexi_url=os.environ.get("NEXI_BASE_URL", "http://192.168.1.9:8001").rstrip("/"),
            media_url=os.environ.get("MEDIA_GATEWAY_URL", "http://192.168.1.9:8090").rstrip("/"),
            sample_rate=int(os.environ.get("XNCH_VOICE_SAMPLE_RATE", "16000")),
            input_device=_device(os.environ.get("XNCH_VOICE_INPUT_DEVICE", "")),
            output_device=_device(os.environ.get("XNCH_VOICE_OUTPUT_DEVICE", "")),
            ws_host=os.environ.get("XNCH_CC_WS_HOST", "127.0.0.1"),
            ws_port=int(os.environ.get("XNCH_CC_WS_PORT", "9001")),
            http_port=int(os.environ.get("XNCH_CC_HTTP_PORT", "9002")),
        )

    def auth_header(self) -> str:
        if self.auth_token:
            token = self.auth_token
            return token if token.startswith("Bearer ") else f"Bearer {token}"
        if self.auth_secret:
            import jwt
            payload = {"sub": self.actor, "iss": "xnch", "exp": int(time.time()) + 3600}
            return f"Bearer {jwt.encode(payload, self.auth_secret, algorithm='HS256')}"
        return f"actor:{self.actor}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest mac/daemon/tests/test_config.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Install deps and commit**

Run: `uv pip install -r mac/requirements.txt` then
```bash
git add mac/
git commit -m "feat(mac): scaffold daemon package with config"
```

---

### Task 2: gateway.py — httpx client for xnch voice + cluster health

**Files:**
- Create: `mac/daemon/gateway.py`
- Test: `mac/daemon/tests/test_gateway.py`

**Interfaces:**
- Consumes: `DaemonConfig` from Task 1.
- Produces: `GatewayClient(config: DaemonConfig, transport: httpx.Transport | None = None)` with:
  - `voice_chat(wav_bytes: bytes, *, session_id: str | None = None, actor_role: str | None = None, return_audio: bool = True) -> dict` — POST multipart `/nexi/voice/chat`; returns parsed JSON (`transcript`, `response`, `session_id`, `audio_base64`).
  - `health() -> dict` — GET `/health` on `base_url`.
  - `nexi_health() -> dict` — GET `/health` on `nexi_url`.
  - `media_health() -> dict` — GET `/health` on `media_url`.
  - `close() -> None`.

- [ ] **Step 1: Write the failing test**

`mac/daemon/tests/test_gateway.py`:
```python
import base64

import httpx

from daemon.config import DaemonConfig
from daemon.gateway import GatewayClient


def _cfg() -> DaemonConfig:
    return DaemonConfig(
        base_url="http://xnch:8001",
        auth_secret="s3cret",
        auth_token="",
        actor="operator",
        nexi_url="http://nexi:8001",
        media_url="http://media:8090",
        sample_rate=16000,
        input_device=None,
        output_device=None,
        ws_host="127.0.0.1",
        ws_port=9001,
        http_port=9002,
    )


def test_voice_chat_builds_multipart_and_parses():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/nexi/voice/chat"
        assert request.method == "POST"
        body = request.content.decode("utf-8", errors="ignore")
        assert "name=\"audio\"" in body
        assert "name=\"session_id\"" in body and "cc-s1" in body
        assert "name=\"actor_role\"" in body and "operator" in body
        return httpx.Response(200, json={
            "transcript": "hello",
            "response": "hi",
            "session_id": "cc-s1",
            "audio_base64": base64.b64encode(b"RIFF").decode(),
        })

    gw = GatewayClient(_cfg(), transport=httpx.MockTransport(handler))
    data = gw.voice_chat(b"\x00\x00", session_id="cc-s1")
    assert data["transcript"] == "hello"
    assert data["session_id"] == "cc-s1"


def test_health_endpoints():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "ok"})

    gw = GatewayClient(_cfg(), transport=httpx.MockTransport(handler))
    assert gw.health()["status"] == "ok"
    assert gw.nexi_health()["status"] == "ok"
    assert gw.media_health()["status"] == "ok"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest mac/daemon/tests/test_gateway.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'daemon.gateway'`

- [ ] **Step 3: Write the implementation**

`mac/daemon/gateway.py`:
```python
"""HTTP client for gate7 xnch and node-b media-gateway."""

from __future__ import annotations

import httpx

from .config import DaemonConfig


class GatewayClient:
    def __init__(self, config: DaemonConfig, transport: httpx.Transport | None = None) -> None:
        self.config = config
        self._http = httpx.Client(base_url=config.base_url, timeout=120.0, transport=transport)

    def close(self) -> None:
        self._http.close()

    def voice_chat(
        self,
        wav_bytes: bytes,
        *,
        session_id: str | None = None,
        actor_role: str | None = None,
        return_audio: bool = True,
    ) -> dict:
        resp = self._http.post(
            "/nexi/voice/chat",
            files={"audio": ("audio.wav", wav_bytes, "audio/wav")},
            data={
                "session_id": session_id or "cc-default",
                "actor_role": actor_role or self.config.actor,
                "return_audio": "true" if return_audio else "false",
            },
        )
        resp.raise_for_status()
        return resp.json()

    def health(self) -> dict:
        resp = self._http.get("/health")
        resp.raise_for_status()
        return resp.json()

    def nexi_health(self) -> dict:
        with httpx.Client(base_url=self.config.nexi_url, timeout=10.0) as client:
            resp = client.get("/health")
            resp.raise_for_status()
            return resp.json()

    def media_health(self) -> dict:
        with httpx.Client(base_url=self.config.media_url, timeout=10.0) as client:
            resp = client.get("/health")
            resp.raise_for_status()
            return resp.json()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest mac/daemon/tests/test_gateway.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add mac/daemon/gateway.py mac/daemon/tests/test_gateway.py
git commit -m "feat(mac): add gateway client for voice chat and cluster health"
```

---

### Task 3: bridge.py — local WebSocket + HTTP push bridge

**Files:**
- Create: `mac/daemon/bridge.py`
- Test: `mac/daemon/tests/test_bridge.py`

**Interfaces:**
- Produces:
  - `start_bridge(on_command: Callable[[dict], None] | None = None, *, host: str = "127.0.0.1", ws_port: int = 9001, http_port: int = 9002) -> None` — starts WS + HTTP servers on background daemon threads; incoming JSON messages from clients are dispatched to `on_command`.
  - `broadcast(payload: dict) -> None` — pushes JSON to all connected WS clients; no-op when no bridge/loop running.

- [ ] **Step 1: Write the failing test**

`mac/daemon/tests/test_bridge.py`:
```python
from daemon import bridge


def test_broadcast_no_clients_is_noop():
    # Calling broadcast before any bridge exists must not raise.
    bridge.broadcast({"type": "status", "text": "x"})


def test_start_bridge_then_broadcast_noop():
    bridge.start_bridge(on_command=None)
    try:
        bridge.broadcast({"type": "status", "text": "ok"})
    finally:
        bridge._bridge_loop.call_soon_threadsafe(bridge._bridge_loop.stop)
        bridge._bridge_loop = None
        bridge._clients.clear()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest mac/daemon/tests/test_bridge.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'daemon.bridge'`

- [ ] **Step 3: Write the implementation**

`mac/daemon/bridge.py`:
```python
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


def _run_http() -> None:
    ThreadingHTTPServer((_HOST, _HTTP_PORT), _Handler).serve_forever()


def start_bridge(
    on_command: Callable[[dict], None] | None = None,
    *,
    host: str = "127.0.0.1",
    ws_port: int = 9001,
    http_port: int = 9002,
) -> None:
    global _bridge_loop, _on_command, _HOST, _WS_PORT, _HTTP_PORT
    _on_command = on_command
    _HOST = host
    _WS_PORT = ws_port
    _HTTP_PORT = http_port
    threading.Thread(target=_run_http, daemon=True).start()
    _bridge_loop = asyncio.new_event_loop()
    threading.Thread(target=_bridge_loop.run_until_complete, args=(_serve(),), daemon=True).start()


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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest mac/daemon/tests/test_bridge.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add mac/daemon/bridge.py mac/daemon/tests/test_bridge.py
git commit -m "feat(mac): add local WS+HTTP bridge with command dispatch"
```

---

### Task 4: segmenter.py — VAD utterance segmentation + garbage filter

**Files:**
- Create: `mac/daemon/segmenter.py`
- Test: `mac/daemon/tests/test_segmenter.py`

**Interfaces:**
- Produces:
  - `VadSegmenter(sample_rate: int = 16000, chunk_ms: int = 30, silence_ms: int = 600, max_ms: int = 15000)` — defaults: `chunk_bytes == 480` (30ms @16k), `silence_limit == 20`, `max_chunks == 500`.
    - `armed: bool` property.
    - `set_armed(armed: bool) -> None`
    - `feed(chunk: bytes, is_speech: bool) -> bytes | None` — returns a completed utterance segment, or `None`. Ignores input while disarmed.
    - `flush() -> bytes | None` — returns any in-progress segment (min-length guarded), or `None`.
  - `is_garbage(text: str) -> bool` — too short or >50% repeated character.

- [ ] **Step 1: Write the failing test**

`mac/daemon/tests/test_segmenter.py`:
```python
from daemon.segmenter import VadSegmenter, is_garbage

CHUNK = 480  # 30ms @ 16kHz int16


def _c(value: int = 1) -> bytes:
    return bytes([value]) * CHUNK


def test_disarmed_ignores_all_frames():
    s = VadSegmenter()
    for _ in range(50):
        assert s.feed(_c(), True) is None
    assert s.flush() is None


def test_segment_ends_after_silence():
    s = VadSegmenter()
    s.set_armed(True)
    for _ in range(30):
        assert s.feed(_c(), True) is None
    for _ in range(20):
        assert s.feed(_c(), False) is None
    seg = s.feed(_c(), False)  # 21st silence chunk trips the limit
    assert seg is not None
    assert len(seg) == CHUNK * 51
    assert not s.armed or s.flush() is None  # utterance consumed


def test_max_duration_caps_segment():
    s = VadSegmenter()
    s.set_armed(True)
    seg = None
    for _ in range(499):
        seg = s.feed(_c(), True)
        if seg is not None:
            break
    assert seg is not None
    assert len(seg) <= CHUNK * 500


def test_flush_returns_partial_utterance():
    s = VadSegmenter()
    s.set_armed(True)
    for _ in range(25):
        assert s.feed(_c(), True) is None
    assert s.flush() is not None


def test_flush_drops_short_segment():
    s = VadSegmenter()
    s.set_armed(True)
    for _ in range(10):
        assert s.feed(_c(), True) is None
    assert s.flush() is None  # < 600ms minimum


def test_garbage_filter():
    assert is_garbage("aa aaa aaa")
    assert is_garbage("ab")
    assert not is_garbage("what is the capital of france")
    assert not is_garbage("okay let me show you the dashboard")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest mac/daemon/tests/test_segmenter.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'daemon.segmenter'`

- [ ] **Step 3: Write the implementation**

`mac/daemon/segmenter.py`:
```python
"""WebRTC-VAD-style utterance segmentation for the capture loop."""

from __future__ import annotations

import collections


class VadSegmenter:
    """Buffers 30ms speech chunks and cuts utterances on trailing silence.

    feed() returns the completed segment (raw int16 PCM) when trailing
    silence reaches silence_ms or the max duration is hit; otherwise None.
    While disarmed, all input is ignored.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        chunk_ms: int = 30,
        silence_ms: int = 600,
        max_ms: int = 15000,
    ) -> None:
        self.sample_rate = sample_rate
        self.chunk_ms = chunk_ms
        self.chunk_bytes = sample_rate * chunk_ms // 1000 * 2
        self.silence_limit = silence_ms // chunk_ms
        self.max_chunks = max_ms // chunk_ms
        self._armed = False
        self._buffer = bytearray()
        self._in_utterance = False
        self._silence = 0
        self._chunks = 0

    @property
    def armed(self) -> bool:
        return self._armed

    def set_armed(self, armed: bool) -> None:
        self._armed = armed

    def feed(self, chunk: bytes, is_speech: bool) -> bytes | None:
        if not self._armed or len(chunk) != self.chunk_bytes:
            return None
        if is_speech and not self._in_utterance:
            self._in_utterance = True
            self._buffer = bytearray()
            self._silence = 0
            self._chunks = 0
        if not self._in_utterance:
            return None
        self._buffer.extend(chunk)
        self._chunks += 1
        self._silence = 0 if is_speech else self._silence + 1
        if self._silence >= self.silence_limit or self._chunks >= self.max_chunks:
            return self.flush()
        return None

    def flush(self) -> bytes | None:
        """Return the in-progress segment (min 600ms), or None."""
        if not self._in_utterance:
            return None
        segment = bytes(self._buffer)
        self._in_utterance = False
        self._buffer = bytearray()
        self._silence = 0
        self._chunks = 0
        if len(segment) < self.chunk_bytes * 20:
            return None
        return segment


def is_garbage(text: str) -> bool:
    """Reject too-short or >50% repeated-character transcripts."""
    chars = text.replace(" ", "")
    if len(chars) < 3:
        return True
    top = collections.Counter(chars).most_common(1)[0][1]
    return top / len(chars) > 0.5
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest mac/daemon/tests/test_segmenter.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add mac/daemon/segmenter.py mac/daemon/tests/test_segmenter.py
git commit -m "feat(mac): add VAD utterance segmenter and garbage filter"
```

---

### Task 5: audio.py — capture loop, wav builder, playback

**Files:**
- Create: `mac/daemon/audio.py`
- Test: `mac/daemon/tests/test_audio.py`

**Interfaces:**
- Consumes: `VadSegmenter` (Task 4), `DaemonConfig` (Task 1).
- Produces:
  - `pcm_to_wav_bytes(pcm: bytes, *, sample_rate: int = 16000) -> bytes`
  - `capture_loop(segmenter: VadSegmenter, config: DaemonConfig, on_segment: Callable[[bytes], None]) -> None` — blocking; streams mic input, feeds `segmenter.feed(frame, is_speech)` with a `webrtcvad.Vad(2)`, calls `on_segment(segment)` for each completed segment. Runs until `KeyboardInterrupt`/exception.
  - `play_wav(wav_bytes: bytes, *, device: int | str | None = None) -> None` — plays via sounddevice.

- [ ] **Step 1: Write the failing test**

`mac/daemon/tests/test_audio.py`:
```python
import io
import wave

from daemon.audio import pcm_to_wav_bytes


def test_pcm_to_wav_bytes_wraps_header():
    pcm = b"\x00\x00" * 1600  # 0.1s @ 16kHz
    wav = pcm_to_wav_bytes(pcm, sample_rate=16000)
    with wave.open(io.BytesIO(wav), "rb") as wf:
        assert wf.getframerate() == 16000
        assert wf.getnchannels() == 1
        assert wf.getnframes() == 1600
        assert wf.readframes(1600) == pcm
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest mac/daemon/tests/test_audio.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'daemon.audio'`

- [ ] **Step 3: Write the implementation**

`mac/daemon/audio.py`:
```python
"""Mic capture, WAV building, and playback for the command center daemon."""

from __future__ import annotations

import io
import queue
import wave
from typing import Callable

import numpy as np

from .config import DaemonConfig
from .segmenter import VadSegmenter


def pcm_to_wav_bytes(pcm: bytes, *, sample_rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return buf.getvalue()


def capture_loop(
    segmenter: VadSegmenter,
    config: DaemonConfig,
    on_segment: Callable[[bytes], None],
) -> None:
    """Blocking mic stream → VAD → segmenter.feed() → on_segment()."""
    import sounddevice as sd
    import webrtcvad

    sample_rate = config.sample_rate
    frame_bytes = segmenter.chunk_bytes
    vad = webrtcvad.Vad(2)
    blocks: queue.Queue = queue.Queue()

    def callback(indata, frames, time_info, status) -> None:
        blocks.put(indata.tobytes())

    with sd.InputStream(
        samplerate=sample_rate,
        channels=1,
        dtype="int16",
        blocksize=frame_bytes,
        device=config.input_device,
        callback=callback,
    ):
        while True:
            block = blocks.get()
            if not segmenter.armed or len(block) < frame_bytes:
                continue
            frame = block[:frame_bytes]
            is_speech = vad.is_speech(frame, sample_rate)
            segment = segmenter.feed(frame, is_speech)
            if segment is not None:
                on_segment(segment)


def play_wav(wav_bytes: bytes, *, device: int | str | None = None) -> None:
    import sounddevice as sd

    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        pcm = wf.readframes(wf.getnframes())
        sr = wf.getframerate()
        channels = wf.getnchannels()
    audio = np.frombuffer(pcm, dtype=np.int16)
    if channels > 1:
        audio = audio.reshape(-1, channels)
    sd.play(audio, sr, device=device)
    sd.wait()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest mac/daemon/tests/test_audio.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add mac/daemon/audio.py mac/daemon/tests/test_audio.py
git commit -m "feat(mac): add mic capture loop, wav builder, playback"
```

---

### Task 6: main.py — daemon orchestration

**Files:**
- Create: `mac/daemon/main.py`
- Test: `mac/daemon/tests/test_main.py`

**Interfaces:**
- Consumes: `DaemonConfig`, `GatewayClient`, `start_bridge`/`broadcast`, `VadSegmenter`/`is_garbage`, `capture_loop`/`play_wav`/`pcm_to_wav_bytes` from Tasks 1-5.
- Produces: `Daemon` class with:
  - `__init__(self, config: DaemonConfig | None = None)` — builds `GatewayClient`, `VadSegmenter`, state `_session_id: str | None`, `_armed: bool`, `_last_transcript: str`.
  - `handle_command(cmd: dict) -> None` — handles `{"type": "arm"}` / `{"type": "disarm"}` / `{"type": "health"}`.
  - `arm() -> None` / `disarm() -> None` — arm segmenter and broadcast status; on disarm, flush and process any segment.
  - `_handle_segment(segment: bytes) -> None` — POST via gateway, broadcast `{"type":"voice_result", ...}`, play returned TTS audio, update `_session_id`, skip garbage/repeat transcripts.
  - `_probe_health() -> dict` — `{"xnch": ..., "nexi": ..., "media": ...}` where each is `"ok" | "err" | "down"`.
  - `health_loop() -> None` — broadcast `{"type":"health","health":...}` every 10s.
  - `run() -> None` — start bridge (with `handle_command`), start health thread, hotkey listener (Caps Lock), then `capture_loop`; returns after capture loop exits.
- `main() -> None` — entrypoint running `Daemon().run()`.

- [ ] **Step 1: Write the failing test**

`mac/daemon/tests/test_main.py`:
```python
from daemon.config import DaemonConfig
from daemon.main import Daemon


def _cfg() -> DaemonConfig:
    return DaemonConfig(
        base_url="http://xnch:8001",
        auth_secret="",
        auth_token="",
        actor="operator",
        nexi_url="http://nexi:8001",
        media_url="http://media:8090",
        sample_rate=16000,
        input_device=None,
        output_device=None,
        ws_host="127.0.0.1",
        ws_port=9001,
        http_port=9002,
    )


def test_arm_disarm_roundtrip():
    d = Daemon(_cfg())
    d.handle_command({"type": "arm"})
    assert d._armed is True
    d.handle_command({"type": "disarm"})
    assert d._armed is False


def test_handle_segment_garbage_is_skipped(monkeypatch):
    d = Daemon(_cfg())
    called = []

    class _FakeGateway:
        def voice_chat(self, *args, **kwargs):
            called.append(True)
            return {}

    d.gateway = _FakeGateway()
    d._handle_segment(b"\x00\x00" * 4800)  # pure silence → empty/garbage transcript
    assert called == []  # gateway not hit because transcript empty/garbage


def test_probe_health_all_down(monkeypatch):
    d = Daemon(_cfg())

    class _DownGateway:
        def health(self):
            raise RuntimeError("down")

        def nexi_health(self):
            raise RuntimeError("down")

        def media_health(self):
            raise RuntimeError("down")

    d.gateway = _DownGateway()
    assert d._probe_health() == {"xnch": "down", "nexi": "down", "media": "down"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest mac/daemon/tests/test_main.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'daemon.main'`

- [ ] **Step 3: Write the implementation**

`mac/daemon/main.py`:
```python
"""XNCH command center daemon — capture → gate7 voice chat → WS broadcast."""

from __future__ import annotations

import base64
import threading
import time

from .audio import capture_loop, pcm_to_wav_bytes, play_wav
from .bridge import broadcast, start_bridge
from .config import DaemonConfig
from .gateway import GatewayClient
from .segmenter import VadSegmenter, is_garbage


class Daemon:
    def __init__(self, config: DaemonConfig | None = None) -> None:
        self.config = config or DaemonConfig.from_env()
        self.gateway = GatewayClient(self.config)
        self.segmenter = VadSegmenter(sample_rate=self.config.sample_rate)
        self._session_id: str | None = None
        self._armed = False
        self._last_transcript = ""

    # --- WS command dispatch -------------------------------------------
    def handle_command(self, cmd: dict) -> None:
        cmd_type = cmd.get("type")
        if cmd_type == "arm":
            self.arm()
        elif cmd_type == "disarm":
            self.disarm()
        elif cmd_type == "health":
            self._broadcast_health()

    # --- push-to-talk ------------------------------------------------
    def arm(self) -> None:
        if self._armed:
            return
        self._armed = True
        self.segmenter.set_armed(True)
        broadcast({"type": "status", "text": "Listening…"})

    def disarm(self) -> None:
        if not self._armed:
            return
        self._armed = False
        self.segmenter.set_armed(False)
        segment = self.segmenter.flush()
        if segment is not None:
            threading.Thread(target=self._handle_segment, args=(segment,), daemon=True).start()

    # --- segment handling --------------------------------------------
    def _handle_segment(self, segment: bytes) -> None:
        wav = pcm_to_wav_bytes(segment, sample_rate=self.config.sample_rate)
        broadcast({"type": "status", "text": "Thinking…"})
        try:
            data = self.gateway.voice_chat(wav, session_id=self._session_id, return_audio=True)
        except Exception as exc:
            broadcast({"type": "status", "text": f"gate7 error: {exc}"})
            return

        transcript = data.get("transcript", "")
        if not transcript or is_garbage(transcript) or transcript == self._last_transcript:
            broadcast({"type": "status", "text": "No new input detected"})
            return
        self._last_transcript = transcript
        self._session_id = data.get("session_id", self._session_id)

        broadcast({
            "type": "voice_result",
            "transcript": transcript,
            "response": data.get("response", ""),
            "session_id": self._session_id,
        })
        audio_b64 = data.get("audio_base64")
        if audio_b64:
            threading.Thread(
                target=play_wav,
                args=(base64.b64decode(audio_b64),),
                kwargs={"device": self.config.output_device},
                daemon=True,
            ).start()

    # --- cluster health ------------------------------------------------
    def _probe_health(self) -> dict:
        result = {"xnch": "down", "nexi": "down", "media": "down"}
        probes = {
            "xnch": lambda: self.gateway.health(),
            "nexi": lambda: self.gateway.nexi_health(),
            "media": lambda: self.gateway.media_health(),
        }
        for name, probe in probes.items():
            try:
                status = probe().get("status")
                result[name] = "ok" if status == "ok" else "err"
            except Exception:
                pass
        return result

    def _broadcast_health(self) -> None:
        broadcast({"type": "health", "health": self._probe_health()})

    def health_loop(self) -> None:
        while True:
            self._broadcast_health()
            time.sleep(10)

    # --- lifecycle -----------------------------------------------------
    def run(self) -> None:
        start_bridge(on_command=self.handle_command,
                     host=self.config.ws_host,
                     ws_port=self.config.ws_port,
                     http_port=self.config.http_port)
        threading.Thread(target=self.health_loop, daemon=True).start()
        broadcast({"type": "status", "text": f"XNCH command center — {self.config.base_url}"})

        try:
            from pynput import keyboard

            listener = keyboard.Listener(on_press=self._hotkey_press,
                                         on_release=self._hotkey_release)
            listener.start()
        except Exception as exc:
            print(f"[cc] hotkey disabled: {exc}")

        capture_loop(self.segmenter, self.config, self._on_capture_segment)

    def _on_capture_segment(self, segment: bytes) -> None:
        threading.Thread(target=self._handle_segment, args=(segment,), daemon=True).start()

    def _hotkey_press(self, key) -> None:
        from pynput import keyboard

        if key == keyboard.Key.caps_lock:
            self.arm()

    def _hotkey_release(self, key) -> None:
        from pynput import keyboard

        if key == keyboard.Key.caps_lock:
            self.disarm()


def main() -> None:
    Daemon().run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest mac/daemon/tests/test_main.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Run the full daemon suite**

Run: `uv run pytest mac/daemon/tests -v`
Expected: PASS (15 passed)

- [ ] **Step 6: Commit**

```bash
git add mac/daemon/main.py mac/daemon/tests/test_main.py
git commit -m "feat(mac): daemon orchestration — voice chat, health loop, hotkey"
```

---

### Task 7: Tauri 2 shell — src-tauri

**Files:**
- Create: `mac/src-tauri/Cargo.toml`
- Create: `mac/src-tauri/build.rs`
- Create: `mac/src-tauri/src/main.rs`
- Create: `mac/src-tauri/tauri.conf.json`
- Create: `mac/src-tauri/.gitignore`

**Interfaces:**
- Produces: a Tauri 2 app shell whose `dev`/`build` compiles; window titled "XNCH Command Center", visible + resizable (no stealth flags).

- [ ] **Step 1: Write the Tauri shell files**

`mac/src-tauri/Cargo.toml`:
```toml
[package]
name = "xnch-command-center"
version = "0.1.0"
edition = "2021"

[build-dependencies]
tauri-build = { version = "2", features = [] }

[dependencies]
tauri = { version = "2", features = [] }
serde = { version = "1", features = ["derive"] }
serde_json = "1"

[profile.release]
panic = "abort"
codegen-units = 1
lto = true
opt-level = "s"
strip = true
```

`mac/src-tauri/build.rs`:
```rust
fn main() {
    tauri_build::build()
}
```

`mac/src-tauri/src/main.rs`:
```rust
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    tauri::Builder::default()
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

`mac/src-tauri/tauri.conf.json`:
```json
{
  "$schema": "https://schema.tauri.app/config/2",
  "productName": "XNCH Command Center",
  "version": "0.1.0",
  "identifier": "systems.xnch.commandcenter",
  "build": {
    "beforeDevCommand": "npm run dev",
    "devUrl": "http://localhost:5173",
    "beforeBuildCommand": "npm run build",
    "frontendDist": "../dist"
  },
  "app": {
    "windows": [
      {
        "title": "XNCH Command Center",
        "width": 900,
        "height": 620,
        "resizable": true,
        "decorations": true
      }
    ],
    "security": {
      "csp": null
    }
  },
  "bundle": {
    "active": true,
    "targets": "all",
    "icon": []
  }
}
```

`mac/src-tauri/.gitignore`:
```
/target
/gen/schemas
```

- [ ] **Step 2: Verify cargo compiles (dry: no frontend yet)**

Run: `cd mac && cargo check --manifest-path src-tauri/Cargo.toml`
Expected: may FAIL at `tauri::generate_context!()` until `frontendDist`/`../dist` and `src-tauri/tauri.conf.json` are consistent — this is expected to surface at Task 8's `npm run build`; if `generate_context!` errors, create `mac/dist/index.html` as a placeholder:
```html
<!doctype html><html><body>XNCH Command Center</body></html>
```
and re-run `cargo check`. Expected: PASS (compiles with no `main.rs` errors).

- [ ] **Step 3: Commit**

```bash
git add mac/src-tauri
git commit -m "feat(mac): add Tauri 2 shell for command center"
```

---

### Task 8: Svelte UI — src/

**Files:**
- Create: `mac/package.json`
- Create: `mac/vite.config.js`
- Create: `mac/index.html`
- Create: `mac/src/main.js`
- Create: `mac/src/App.svelte`
- Create: `mac/src/app.css` (optional minimal)

**Interfaces:**
- Consumes: WS `ws://127.0.0.1:9001` broadcast messages `{"type":"status","text"}`, `{"type":"health","health":{"xnch","nexi","media"}}`, `{"type":"voice_result","transcript","response"}`; sends `{"type":"arm"}` / `{"type":"disarm"}`.
- Produces: `npm run build` → `mac/dist/` (Tauri `frontendDist`), `npm run dev` → dev server on :5173.

- [ ] **Step 1: Write the frontend files**

`mac/package.json`:
```json
{
  "name": "xnch-command-center",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "tauri": "tauri"
  },
  "devDependencies": {
    "@sveltejs/vite-plugin-svelte": "^5.0.0",
    "@tauri-apps/cli": "^2.0.0",
    "svelte": "^5.0.0",
    "vite": "^6.0.0"
  }
}
```

`mac/vite.config.js`:
```js
import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

export default defineConfig({
  plugins: [svelte()],
  server: { port: 5173, strictPort: true },
  clearScreen: false,
});
```

`mac/index.html`:
```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>XNCH Command Center</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/main.js"></script>
  </body>
</html>
```

`mac/src/main.js`:
```js
import { mount } from 'svelte';
import App from './App.svelte';

const app = mount(App, { target: document.getElementById('app') });
export default app;
```

`mac/src/App.svelte`:
```svelte
<script>
  import { onMount } from 'svelte';

  let ws;
  let status = 'Daemon offline — run: cd mac && uv run python -m daemon.main';
  let daemonOnline = false;
  let listening = false;
  let health = { xnch: null, nexi: null, media: null };
  let transcript = '';
  let response = '';

  function connect() {
    ws = new WebSocket('ws://127.0.0.1:9001');
    ws.onopen = () => {
      daemonOnline = true;
      status = 'Connected — hold the button or Caps Lock to talk';
    };
    ws.onclose = () => {
      daemonOnline = false;
      status = 'Daemon offline — run: cd mac && uv run python -m daemon.main';
    };
    ws.onmessage = (e) => {
      const m = JSON.parse(e.data);
      if (m.type === 'status') status = m.text || status;
      if (m.type === 'health') health = m.health;
      if (m.type === 'voice_result') {
        transcript = m.transcript || '';
        response = m.response || '';
        listening = false;
      }
    };
  }

  function send(cmd) {
    if (ws && ws.readyState === 1) ws.send(JSON.stringify(cmd));
  }

  function arm() {
    listening = true;
    send({ type: 'arm' });
  }

  function disarm() {
    send({ type: 'disarm' });
  }

  onMount(() => {
    connect();
    return () => ws?.close();
  });
</script>

<main class="cc">
  <header>
    <span class="dot {daemonOnline ? 'ok' : 'down'}"></span>
    <span class="status">{status}</span>
  </header>

  <section class="health">
    {#each ['xnch', 'nexi', 'media'] as name}
      <div class="card">
        <span class="label">{name}</span>
        <span class="val {health[name] === 'ok' ? 'ok' : health[name] ? 'err' : 'unknown'}">
          {health[name] ?? '…'}
        </span>
      </div>
    {/each}
  </section>

  <button
    class="ptt {listening ? 'active' : ''}"
    on:mousedown={arm}
    on:mouseup={disarm}
    on:mouseleave={disarm}
    on:touchstart={(e) => { e.preventDefault(); arm(); }}
    on:touchend={disarm}
  >
    {listening ? 'Listening…' : 'Hold to talk'}
  </button>

  {#if transcript}<p class="you">you: {transcript}</p>{/if}
  {#if response}<p class="nexi">nexi: {response}</p>{/if}
</main>

<style>
  :global(body) { margin: 0; background: #0b0f14; color: #e6edf3; font-family: -apple-system, 'SF Pro Text', sans-serif; }
  .cc { display: flex; flex-direction: column; gap: 16px; padding: 20px; min-height: 100vh; box-sizing: border-box; }
  header { display: flex; align-items: center; gap: 8px; font-size: 13px; color: #8b949e; }
  .dot { width: 10px; height: 10px; border-radius: 50%; }
  .dot.ok { background: #3fb950; }
  .dot.down { background: #f85149; }
  .health { display: flex; gap: 12px; }
  .card { flex: 1; border: 1px solid #21262d; border-radius: 10px; padding: 12px 14px; background: #161b22; }
  .label { display: block; font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; color: #8b949e; margin-bottom: 4px; }
  .val.ok { color: #3fb950; font-weight: 600; }
  .val.err { color: #d29922; }
  .val.unknown { color: #8b949e; }
  .ptt { margin-top: auto; padding: 18px; border-radius: 12px; border: none; background: #21262d; color: #e6edf3; font-size: 16px; font-weight: 600; cursor: pointer; }
  .ptt.active { background: #1f6feb; }
  .you { color: #8b949e; font-size: 13px; }
  .nexi { color: #e6edf3; font-size: 14px; line-height: 1.5; white-space: pre-wrap; }
</style>
```

- [ ] **Step 2: Install frontend deps and build**

Run: `cd mac && npm install && npm run build`
Expected: `npm run build` succeeds and writes `mac/dist/`.

- [ ] **Step 3: Verify Tauri compiles end-to-end**

Run: `cd mac && cargo check --manifest-path src-tauri/Cargo.toml`
Expected: PASS (Rust + generated context from `../dist`).

- [ ] **Step 4: Commit**

```bash
git add mac/package.json mac/vite.config.js mac/index.html mac/src mac/dist/index.html
git commit -m "feat(mac): add Svelte command center UI"
```

---

### Task 9: README + end-to-end verification

**Files:**
- Create: `mac/README.md`

- [ ] **Step 1: Write the README**

`mac/README.md`:
```markdown
# XNCH Command Center (mac)

Thin-client command center for xnchSystems on the Mac. All compute (STT, TTS,
LLM, media) stays on the cluster; the Mac only captures audio, calls gate7,
and shows status.

## Layout

- `src/` — Svelte 5 UI (status, cluster health, push-to-talk)
- `src-tauri/` — Tauri 2 shell
- `daemon/` — Python capture daemon (VAD → POST /nexi/voice/chat → WS broadcast)

## Run

```bash
uv pip install -r requirements.txt          # one-time
source ~/.xnch/xnch.env                     # XNCH_BASE_URL, XNCH_AUTH_SECRET, ...
PYTHONPATH="$PWD" uv run python -m daemon.main   # terminal 1: daemon (WS :9001)
npm install                                  # one-time
npm run tauri dev                            # terminal 2: app
```

## Voice

Hold the in-app button or Caps Lock to talk. Release when done — the daemon
POSTs the utterance to gate7 `POST /nexi/voice/chat` and plays the TTS reply.

## Status

xnch / nexi / media cards refresh every 10s from the daemon health probe.
```

- [ ] **Step 2: Manual end-to-end verification**

1. Start daemon: `cd mac && source ~/.xnch/xnch.env && PYTHONPATH="$PWD" uv run python -m daemon.main`
   Expected: prints no error; `curl http://127.0.0.1:9001` (HTTP mirror) returns the mobile page.
2. Start app: `cd mac && npm run tauri dev`
   Expected: window opens, dot turns green, health cards populate (xnch ok if gate7 reachable).
3. Hold the in-app button (or Caps Lock), speak, release.
   Expected: status → "Thinking…", transcript + Nexi response appear, TTS audio plays.
4. If `media` shows down and media-gateway binds `127.0.0.1` on node-b: expected — reach it via cluster/SSH or set `MEDIA_GATEWAY_BIND` on node-b. Not blocking.

- [ ] **Step 3: Run the full daemon test suite once more**

Run: `uv run pytest mac/daemon/tests -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add mac/README.md
git commit -m "docs(mac): command center run instructions"
```

---

## Self-Review Notes

- **Spec coverage:** shell (Task 7), Svelte UI (Task 8), daemon audio/VAD (Tasks 4-5), gateway (Task 2), bridge (Task 3), config (Task 1), orchestration + health (Task 6), docs (Task 9). Deferred per spec: dashboard embed, media controls, speaker verification, screen capture.
- **Type consistency:** `DaemonConfig` fields fixed in Task 1 and reused verbatim in Tasks 2/5/6 tests. `VadSegmenter.armed/set_armed/feed/flush` consistent across Tasks 4/5/6. `start_bridge(on_command=...)` signature consistent Task 3/6.
- **No placeholders:** all code provided inline.
