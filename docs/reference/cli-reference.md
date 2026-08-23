# CLI Reference

Sources: `cli/main.py`, `cli/voice.py` (Typer), `xnch-train/xnch_train/cli.py`,
`scripts/`. Console scripts registered by the root `pyproject.toml`:
**`xnch-cli`, `xnch-mcp`, `fs-read-agent`, `exec-agent`, `docs-test-mcp`**
(run via `uv run <name>`); module forms `python -m cli`, `python -m xnch_mcp`
are equivalent.

> Fresh-clone caveat [UNVERIFIED remedy]: the CLI imports the `xnch` submodule
> package at runtime (`cli/client.py` → `xnch.routing…`), so a bare root
> `uv sync` is not enough — make `./xnch` importable (e.g. `PYTHONPATH=./xnch`)
> **and** provide its runtime deps (redis, …). Operator hosts carry the full
> env; `xtrain` is self-contained inside `xnch-train/`.

## `xnch-cli` — xnch CLI client

Targets xnch :8001; persists a session locally.

| Command | Purpose |
|---|---|
| `health` | xnch health check |
| `status [--json]` | system/LLM status summary |
| `chat [MESSAGE]` | one-shot chat through `/nexi/chat` |
| `run` | interactive chat loop |
| `auth token` | mint/print an actor bearer token |
| `memory recall <query>` | semantic recall via `/nexi/memory/recall` |
| `memory surface` | memory surface view |
| `session show` / `session clear` | inspect/reset CLI session state |
| `consolidate status` | systemd consolidation timer status |
| `mcp servers` | bridge server inventory (connected/enabled/tools) |
| `mcp tools [--server ID]` | merged native+bridged tool list |
| `mcp call NAME [ARGS...]` | invoke a tool from the shell |
| `mcp test` | canned MCP/chat routing tests (`cli/mcp_tests.py`) |
| `voice devices` | list audio devices |
| `voice mic-test` | microphone level test |
| `voice speaker-test` | TTS playback test |
| `voice listen` | push-to-talk → transcribe |
| `voice speak TEXT` | text → speech |
| `voice talk` | full voice loop (push-to-talk → chat → speak) |

Voice setup on macOS: `scripts/setup-mac-voice-client.sh`,
models via `scripts/install-voice-models.sh`; guide:
[voice](../guides/voice.md).

## `xtrain` — training pipeline CLI

Typer app, Phase 0 surfaces. Requires `XTRAIN_PSEUDONYMIZE_SECRET`.

```
cd xnch-train
export XTRAIN_PSEUDONYMIZE_SECRET='<secret>'   # required for real commands
uv run xtrain --help                           # VERIFIED: typer app loads
uv run xtrain validate-dataset DIRECTORY            # manifest gate; exit 0/1
uv run xtrain extract --out DIR [--pg-dsn DSN] [--skip-langfuse]
uv run xtrain suite --out FILE [--cutoff ISO-DATE]  # starter suite JSON
uv run xtrain baseline --base-url URL --model ID --suite FILE --out FILE \
                    [--checkpoint-id NAME] [--fake-reply TEXT]
```

Per-subcommand flags are visible via `--help`. Full walkthrough:
[run-eval guide](../guides/run-eval.md).

## scripts/

| Script | Purpose |
|---|---|
| `scripts/deploy.sh` | deploy helper (submodule checkout + service sync) |
| `scripts/setup-mac-voice-client.sh` | Mac voice client bootstrap |
| `scripts/install-voice-models.sh` | download whisper/piper models |
| `scripts/test-nexi-mcp.sh` | smoke the nexi MCP tool path |
| `scripts/audit-memory-overlap.py` | memory overlap audit report |
| `scripts/openevolve_persona_trial.sh` | persona experiment harness |
| `scripts/agent-gateway/` | standalone agent-gateway mini-package (own pyproject) |

Infra boot scripts (on nodes): `start-node-a.sh`, `start-node-b.sh`,
`wake-node-b.sh`, `setup-gpu-driver.sh`, `e2e-test.sh` — documented in
[deploy guides](../guides/deploy-node-a.md) and
[topology](../architecture/topology.md#boot-order).
