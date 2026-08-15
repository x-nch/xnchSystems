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
