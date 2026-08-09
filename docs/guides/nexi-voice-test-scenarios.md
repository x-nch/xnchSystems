# Nexi Voice — Test Scenarios (gate7)

Copy-paste checks for the voice stack after deploy. Assumes gate7 with
`xnch.service` on `:8001`, Piper at `~/.local/bin/piper`, and Whisper in the
xnch venv.

**Related:** [voice architecture](nexi-voice-architecture.md) · [deploy runbook](../runbooks/voice-deploy.md)

```bash
cd /home/x-nch/xnchSystems
PY=/home/x-nch/xnchSystems/.venv/bin/python
API=http://127.0.0.1:8001
```

---

## 1. Smoke — service and routes

```bash
curl -sf "$API/health"
curl -sf "$API/nexi/capabilities" | jq '.voice // .capabilities.voice // .'
```

**Expect:** `health` 200; capabilities mention voice (STT/TTS) when enabled.

---

## 2. TTS only — `/nexi/voice/speak`

```bash
curl -sf -X POST "$API/nexi/voice/speak" \
  -H 'Content-Type: application/json' \
  -d '{"text":"Nexi voice online"}' -o /tmp/nexi-speak.wav
file /tmp/nexi-speak.wav
aplay /tmp/nexi-speak.wav   # or: $PY -m cli voice speak "Nexi voice online"
```

**Expect:** RIFF WAVE, ~50–150 KB; audible speech.

| Failure | Check |
|---------|--------|
| 503 Voice disabled | `XNCH_VOICE_ENABLED=true` in `~/.xnch/xnch.env`, restart xnch |
| piper not found | `PATH` includes `~/.local/bin` in `xnch.env` |
| libespeak-ng | Use `~/.local/bin/piper` wrapper |

---

## 3. STT only — `/nexi/voice/transcribe`

Generate a speech sample (no mic required):

```bash
espeak-ng -w /tmp/hello.wav "Hello Nexi, what is the weather today?"
curl -s -X POST "$API/nexi/voice/transcribe" \
  -F 'audio=@/tmp/hello.wav' -F 'format=wav' -F 'sample_rate=22050' | jq .
```

**Expect:** HTTP 200, non-empty `transcript` (minor name drift OK, e.g. "Maxi").

| Input | Expect |
|-------|--------|
| Tone/silence WAV | HTTP 400, `Empty transcript` |
| Real speech WAV | HTTP 200, transcript text |

First request may take 10–30s while Whisper loads.

---

## 4. Full loop — `/nexi/voice/chat`

```bash
curl -s -X POST "$API/nexi/voice/chat" \
  -F 'audio=@/tmp/hello.wav' \
  -F 'session_id=voice-test-1' \
  -F 'actor_role=operator' \
  -F 'return_audio=true' | jq '{transcript, response, model_used, audio_len:(.audio_base64|length)}'
```

Decode reply audio:

```bash
curl -s -X POST "$API/nexi/voice/chat" \
  -F 'audio=@/tmp/hello.wav' \
  -F 'session_id=voice-test-2' \
  -F 'actor_role=operator' \
  -F 'return_audio=true' \
| python3 -c "
import sys, json, base64
d=json.load(sys.stdin)
open('/tmp/nexi-reply.wav','wb').write(base64.b64decode(d['audio_base64']))
print(d['transcript']); print(d['response'][:200])
"
aplay /tmp/nexi-reply.wav
```

**Expect:** transcript from STT, text `response` from Ornith, `audio_base64` non-empty,
`model_used` e.g. `ornith`.

---

## 5. CLI — gate7 operator

```bash
$PY -m cli voice devices
$PY -m cli voice speak "Hello ck-san"
$PY -m cli voice listen --duration 5    # records 5s, prints transcript
$PY -m cli voice talk --once              # one push-to-talk round trip
$PY -m cli voice talk                     # interactive (Space = hold to talk)
```

**Expect:** devices list pulse/default; speak plays audio; talk returns Nexi reply
spoken aloud.

| Failure | Fix |
|---------|-----|
| PortAudio not found | `sudo apt install libportaudio2` |
| No input device | Check PulseAudio / `voice devices` |

---

## 6. Tool routing via voice

Use a spoken prompt that forces a tool (same patterns as [nexi-test-prompts](nexi-test-prompts.md)):

```bash
espeak-ng -w /tmp/search.wav "Use xnch web search for vLLM latest release notes and summarize in one sentence."
curl -s -X POST "$API/nexi/voice/chat" \
  -F 'audio=@/tmp/search.wav' \
  -F 'session_id=voice-tools-1' \
  -F 'actor_role=operator' \
  -F 'return_audio=false' | jq '{transcript, response, model_used}'
```

**Expect:** response cites live search results, not hallucinated versions.

---

## 7. Memory / recall via voice

```bash
espeak-ng -w /tmp/recall.wav "Recall memory MCP bridge deploy and summarize."
curl -s -X POST "$API/nexi/voice/chat" \
  -F 'audio=@/tmp/recall.wav' \
  -F 'session_id=voice-recall-1' \
  -F 'actor_role=operator' | jq '{transcript, response}'
```

**Expect:** recall path hit (episodic or curated per routing rules); grounded summary.

---

## 8. Error and edge cases

| Scenario | Command | Expect |
|----------|---------|--------|
| Voice disabled | unset `XNCH_VOICE_ENABLED`, restart | 503 on voice routes |
| Empty audio | `curl -F 'audio=@/dev/null'` | 400 validation error |
| Oversized upload | > `XNCH_VOICE_MAX_AUDIO_BYTES` | 413 or 400 |
| `return_audio=false` | omit TTS in chat | JSON only, no `audio_base64` |
| Session continuity | same `session_id` twice | second turn references first |

---

## 9. Performance baselines (gate7 CPU)

| Step | Typical |
|------|---------|
| Whisper cold start | 10–30s first call |
| STT (2–3s clip) | &lt;1s warm |
| LLM (Ornith via LiteLLM) | 1–5s |
| Piper TTS (~1 sentence) | &lt;2s |
| End-to-end voice chat | 3–15s warm |

---

## 10. Regression (CI)

```bash
cd /home/x-nch/xnchSystems
pytest tests/test_voice_api.py xnch/tests/test_voice_audio.py -q
```

**Expect:** all green without GPU or Piper binary (mocked in tests).
