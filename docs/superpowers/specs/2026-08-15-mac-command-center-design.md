# Mac Command Center — Phase 1 Design

Date: 2026-08-15
Status: Approved in chat (2026-08-15)

## Purpose

Turn the Mac (Apple M2, 8GB RAM) into the **command center** for xnchSystems:
the operator's eyes, ears, and console. This phase builds the spine: a native
Tauri app shell + a Python capture daemon that give one place to run voice,
watch cluster status, and launch the rest (dashboard, media) in later phases.

## Constraints

- **Thin controller** — the Mac captures and controls; all compute (STT, TTS,
  LLM, media generation, speaker verification) stays on the cluster
  (gate7 xnch :8001, node-b media-gateway :8090).
- **One native app** — Tauri 2 shell, borrowed from
  `~/work/covert-copilot` (proven toolchain: cargo 1.95, node on this Mac).
- 8GB RAM — keep the app + daemon light; no local inference.

## Architecture

```
Mac (Tauri app + Python daemon)
  Tauri shell ── menu bar / visible window ── Svelte UI
       │                                        ▲
       │   WS :9001 (status/events)             │
  daemon/audio_loop ── VAD ── segment ──────────┘
       │   POST /nexi/voice/chat (wav bytes)
gate7 xnch :8001 ── STT (Whisper) → Nexi → TTS (Piper)
       └── returns transcript + response + audio_base64 (played on Mac)
```

- Voice path reuses the existing gate7 API already proven by `cli/voice.py`:
  `POST /nexi/voice/chat`.
- Config via `~/.xnch/xnch.env` (same pattern as
  `docs/guides/nexi-voice-mac-client.md`).

## Components

### 1. `mac/src-tauri/` — Tauri 2 shell (borrowed)

Borrow `Cargo.toml`, `tauri.conf.json`, `main.rs`, `build.rs` from
`~/work/covert-copilot/client/src-tauri/` and adapt:

- Remove stealth flags: `contentProtected`, `alwaysOnTop`, `skipTaskbar`,
  `focus:false`, `decorations:false`, `macOSPrivateApi`.
- Visible, resizable window + menu bar / tray.
- New bundle identifier (e.g. `systems.xnch.commandcenter`).
- App icon (placeholder ok in phase 1).

### 2. `mac/src/` — Svelte UI

Rewrite of covert-copilot's overlay into a command-center surface:

- **Cluster status card**: health of xnch (`GET /health`), nexi, and
  media-gateway (`GET /media-gateway/health`), resolved via daemon.
- **Push-to-talk button** + global hotkey: hold to record, release to send.
- **Transcript + Nexi response** display.
- **Daemon status** via WS :9001.

### 3. `mac/daemon/` — Python capture daemon (ported)

Borrow from `~/work/covert-copilot/client/`:

- `audio_loop.py` — WebRTC VAD loop (30ms chunks, 600ms trailing silence =
  end of utterance, 15s cap), garbage filter, transcript dedup,
  thread-per-utterance. Replace local `stt.transcribe()` with
  `POST /nexi/voice/chat`.
- `bridge.py` — WS :9001 + HTTP :9002 push bridge (reconnecting clients,
  mobile mirror), ported as-is.
- `config.py` — `XNCH_BASE_URL`, `XNCH_AUTH_SECRET`, input/output device,
  hotkey, sample rate (16kHz).
- `health.py` — health probe for xnch / nexi / media-gateway (drives the
  status card).

### Not borrowed

- `stt.py` + mlx-whisper (violates thin-controller; RAM cost on 8GB M2).
- `server/` FastAPI (xnch already owns the API, adapters, memory).
- `speaker.py` (phase 2, runs on gate7 for operator-only listening).
- Stealth overlay behavior (command center is a visible app).

## Voice Interaction (Phase 1)

- **Push-to-talk**: hold hotkey/button → VAD segments within the window →
  utterance sent to gate7 → transcript + Nexi response + TTS audio played
  back on the Mac speaker.
- Always-on VAD mode and operator-verification are **deferred** to phase 2.

## Out of Scope (Phase 2+)

- Embed the existing Next.js dashboard (WKWebView) in the app.
- Media controls for media-gateway (Flux/Wan jobs).
- Operator-only listening (speaker verification on gate7).
- Screen capture feeding xnch perception.

## Error Handling

- Daemon cannot reach gate7 → status card shows unreachable; WS pushes
  status; no crash.
- Mic permission missing → surfaced in UI with pointer to
  System Settings → Privacy → Microphone.
- Silent capture → warn (peak/rms stats, same hint text as `cli/voice.py`).
- WS client reconnect with backoff (already in covert-copilot bridge).

## Testing

- Unit tests for daemon: VAD segmentation, garbage filter, dedup,
  config parsing, health probe response parsing.
- `cargo build` / `cargo tauri dev` compiles.
- Manual end-to-end: daemon + app → push-to-talk → audible TTS reply from
  gate7 (API path already proven by `cli voice talk`).

## Files

```
mac/
  src-tauri/            # Tauri 2 shell (adapted from covert-copilot)
  src/                  # Svelte UI
  daemon/
    __init__.py
    config.py           # env/config, XNCH_BASE_URL etc.
    audio_loop.py       # VAD loop → POST /nexi/voice/chat
    bridge.py           # WS :9001 + HTTP :9002
    health.py           # cluster health probes
    gateway.py          # httpx client for xnch + media-gateway
  requirements.txt
  README.md
```
