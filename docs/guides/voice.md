# Voice

Audience: users running the voice loop. Sources: `cli/voice.py`,
`xnch/routes/voice.py`, `scripts/{setup-mac-voice-client,install-voice-models}.sh`,
and the detailed guides kept alongside:
[architecture](nexi-voice-architecture.md) ·
[Mac client](nexi-voice-mac-client.md) ·
[test scenarios](nexi-voice-test-scenarios.md) ·
[deploy runbook](../runbooks/voice-deploy.md).

## Topology in one line

Mic/speaker live on your Mac (`cli voice`); STT/TTS run on gate7 CPU
(whisper `base` int8 + piper); the chat itself is the normal `/nexi/chat`
loop. Full component diagram: [voice architecture](nexi-voice-architecture.md).

## Fast path (Mac client)

Voice subcommands need the root `voice`/`voice-client` dependency groups
(`uv sync --all-groups`) plus an env where the `xnch` package is importable —
the Mac setup script provisions this ([Mac client guide](nexi-voice-mac-client.md)).

```bash
# one-time on the Mac
./scripts/setup-mac-voice-client.sh          # deps + config; targets gate7 :8001
./scripts/install-voice-models.sh            # whisper + piper models server-side

# sanity
uv run xnch-cli voice devices           # pick mic/speaker ids
uv run xnch-cli voice mic-test
uv run xnch-cli voice speaker-test

# the loop
uv run xnch-cli voice talk              # push-to-talk -> transcribe -> chat -> speak
uv run xnch-cli voice listen            # transcribe only
uv run xnch-cli voice speak "text"      # TTS only
```

HTTP-only alternative: `POST /nexi/voice/transcribe|speak|chat` — caps and
models under `XNCH_VOICE_*` ([env reference](../reference/env-vars.md#voice)).

## Verification checklist

Work through [test scenarios](nexi-voice-test-scenarios.md): smoke →
STT/TTS isolated → full loop → CLI flags → tool routing over voice.

## Troubleshooting quick hits

| Symptom | First check |
|---|---|
| no devices listed | PortAudio perms (macOS mic consent) |
| transcribe 413 | audio exceeds `XNCH_VOICE_MAX_AUDIO_BYTES`/`_DURATION_S` |
| TTS silent | piper voice path exists? `XNCH_VOICE_TTS_VOICE_PATH` |
| wrong node targeted | Mac client must hit gate7's home-LAN IP, not 50.1 ([topology](../architecture/topology.md#network-planes)) |
