# Nexi voice — deploy and verify on gate7

## Prerequisites

```bash
cd /home/x-nch/xnchSystems

# STT (xnch service venv)
cd xnch && uv pip install --python .venv/bin/python faster-whisper numpy

# CLI mic/playback (repo venv)
cd .. && uv pip install --python .venv/bin/python sounddevice numpy

# ALSA + PulseAudio (mic/speaker access)
sudo apt-get install -y alsa-utils libportaudio2 portaudio19-dev pulseaudio pulseaudio-utils
sudo usermod -aG audio "$USER"
# Log out and back in once so PulseAudio sees the Intel PCH card (not auto_null)

# Piper voice + binary
./scripts/install-voice-models.sh
# Piper binary: ~/.local/bin/piper (wrapper sets LD_LIBRARY_PATH to ~/.local/piper)
```

Ensure `~/.xnch/xnch.env` includes voice settings (see architecture doc).

## Deploy

```bash
sudo systemctl restart xnch.service
curl -sf http://127.0.0.1:8001/health
curl -sf -X POST http://127.0.0.1:8001/nexi/voice/speak \
  -H 'Content-Type: application/json' \
  -d '{"text":"Nexi voice online"}' -o /tmp/nexi-speak.wav
file /tmp/nexi-speak.wav
```

## CLI

On **gate7** (mic attached to server):

```bash
cd /home/x-nch/xnchSystems
python -m cli voice devices
python -m cli voice speak "Hello ck-san"
python -m cli voice talk --once
```

On **MacBook** (mic/speaker local, STT/TTS on gate7): see
[Mac client guide](../guides/nexi-voice-mac-client.md) or run
`./scripts/setup-mac-voice-client.sh`.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `404` on `/nexi/voice/*` | `sudo systemctl restart xnch` |
| `piper not found` | Check `PATH` in `xnch.env` includes `~/.local/bin` |
| `libespeak-ng.so.1` | Use `~/.local/bin/piper` wrapper (bundled libs in `~/.local/piper`) |
| STT slow first call | Whisper model loads on first request (~10–30s) |
| `TTS unavailable` | `echo test \| piper --model ~/.xnch/voice/en_US-lessac-medium.onnx --output_file /tmp/t.wav` |
| `no soundcards found` / `auto_null` only | `groups` must include `audio`; log out/in, then `arecord -l` |
| `PortAudio library not found` | `sudo apt install libportaudio2` |
| Mic silent | `amixer -c 0 cset name='Input Source' 'Internal Mic'`; raise Capture volume |
| No audio on 3.5mm jack | Plug jack, `pactl set-default-sink alsa_output.pci-0000_00_1f.3.analog-stereo`, `amixer -c 0 set Headphone 90% unmute`. Prefer `export XNCH_VOICE_OUTPUT_DEVICE=14` (pulse) or leave unset — not `0` unless needed |
| `Invalid sample rate` on playback | Piper is 22050 Hz; raw ALSA hw device `0` needs resampling — fixed in CLI, or use pulse (`14`) |
| Same Nexi reply every turn | Stale session — `voice talk` now starts fresh; use `--continue` to keep old session |
| PulseAudio null sink until re-login | `sg audio -c 'pulseaudio --kill; pulseaudio --start'` (temporary) |
