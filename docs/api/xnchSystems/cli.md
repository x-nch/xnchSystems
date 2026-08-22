# xnch CLI — `python -m cli` (alias `xnch-cli`)

Typer CLI that talks to the xnch control plane. Entrypoints: `python -m cli`
(`cli/__main__.py`), or the installed `xnch-cli` console script (from
`pyproject.toml`: `xnch-cli = "cli.main:app"`).

The CLI mints its own auth token from env (see [auth.md](auth.md)); it never
needs an interactive login.

## Configuration (env vars)

Read by `cli/config.py` (`CliConfig.from_env()`):

| Env var | Default | Meaning |
|---------|---------|---------|
| `XNCH_BASE_URL` | `http://localhost:8001` | xnch base URL (Mac setup uses `http://192.168.1.10:8001`) |
| `NEXI_BASE_URL` | `http://localhost:8000` | nexi base URL (only used by `health --nexi`) |
| `XNCH_AUTH_SECRET` | — | shared secret for HS256 JWT minting |
| `XNCH_AUTH_TOKEN` | — | pre-issued bearer token (used verbatim if set) |
| `XNCH_ACTOR` | `operator` | actor id embedded in minted tokens / `actor:<id>` fallback |

Voice: `XNCH_VOICE_SAMPLE_RATE`, `XNCH_VOICE_INPUT_DEVICE`, `XNCH_VOICE_MUTE`
(see `cli/voice.py`).

State: session id persisted to `~/.xnch/cli_state.json`.

## Command tree

```
xnch-cli
├── health [--nexi] [--json]
├── status [--json]
├── run  <text...> [--priority NORMAL|CRITICAL] [--json]
├── chat [text...] [--stream|-s] [--session ID] [--new-session]
│         [--continue|-c] [--json]
├── auth
│   └── token [--actor ID] [--ttl SECONDS]
├── memory
│   ├── recall <query...> [--top-k N] [--unique/--all] [--json]
│   └── surface [--json]
├── session
│   ├── show [--json]
│   └── clear [--json]
├── consolidate
│   └── status [--json]
├── mcp
│   ├── servers [--actor nexi] [--json]
│   ├── tools [--actor nexi] [--prefix STR] [--json]
│   ├── call <tool_name> [--arg key=value ...] [--actor nexi] [--json]
│   └── test [--skip-chat] [--json]
└── voice
    ├── devices [--json]
    ├── mic-test [--seconds N] [--json]
    ├── listen [--seconds N] [--transcribe] [--json]
    ├── speaker-test [--file PATH] [--json]
    ├── speak <text...> [--json]
    └── talk [--once] [--push-to-talk] [--model MODEL] [--json]
```

## Commands

### `health`
Check xnch (and with `--nexi`, nexi) health.
```bash
python -m cli health
python -m cli health --nexi --json
```

### `status`
Show `system_state_version` and `policy_version` (GET `/system/state`).
```bash
python -m cli status
```

### `run`
Run the decision pipeline via POST `/session/init`. `raw_input` is the
intent/command text (multiple words are joined).
```bash
python -m cli run "summarize today's memory consolidation"
python -m cli run "high priority task" --priority CRITICAL --json
```
Prints `status`, and any of `decision_id`, `execution_ref`, `audit_ref`,
`hold_id`, `error` present in the response.

### `chat`
Chat with Nexi via POST `/nexi/chat` (or `/nexi/chat/stream` with `--stream`).

```bash
python -m cli chat "what changed in nexi this week"
python -m cli chat --stream --new-session "explain the pipeline"
python -m cli chat  # interactive REPL (Ctrl+C / /quit exits; /recall <q> triggers memory recall)
```

Session handling:
- default one-shot: reuses the stored session id if one exists, else creates one
- `--new-session`: mint `cli-<uuid>` and persist
- `--continue` / `-c`: force-reuse stored session (no auto new)
- `--session ID`: explicit override

### `auth token`
Mint an HS256 dev token (requires `XNCH_AUTH_SECRET`).
```bash
python -m cli auth token --actor operator --ttl 3600
```
Prints `Bearer <jwt>` for use as `export XNCH_AUTH_TOKEN="Bearer <jwt>"`.

### `memory recall`
Semantic recall via POST `/nexi/memory/recall` (`{query, top_k}`).
```bash
python -m cli memory recall "guardrail tuning decisions" --top-k 5
python -m cli memory recall "all episodes" --all
```
Prints `[i] similarity=… type=…` + first 300 chars of content. `--unique`
dedupes identical episode content.

### `memory surface`
Show pending proactivity events (GET `/nexi/memory/surface`).
```bash
python -m cli memory surface --json
```

### `session show` / `session clear`
Inspect or reset the persisted session id (`~/.xnch/cli_state.json`). Server
has no clear endpoint; a fresh `cli-<uuid>` avoids stale context.
```bash
python -m cli session show
python -m cli session clear
```

### `consolidate status`
Show the last consolidation run from the `02:00 UTC` daily systemd timer
(`consolidation.timer` / `consolidation.service`) via local `systemctl` +
`journalctl`.
```bash
python -m cli consolidate status
```

### `mcp servers` / `mcp tools` / `mcp call`
Introspect and invoke the MCP bridge (see [endpoints.md](endpoints.md), `/mcp/*`).

```bash
python -m cli mcp servers --actor nexi
python -m cli mcp tools --actor nexi --prefix crg
python -m cli mcp call crg_list_graph_stats_tool --actor nexi
python -m cli mcp call crg_semantic_search_nodes_tool --arg 'query=McpBridgePool' --arg 'limit=3'
```
`--arg` is `key=value`; values that parse as JSON are sent as JSON.

### `mcp test`
Run the MCP bridge integration suite (`cli/mcp_tests.py`): `MCP_TOOL_TESTS`
(servers, tool count, xnch_health, crg graph, agentmemory, docs, web search)
plus, unless `--skip-chat`, `CHAT_TESTS` that drive `/nexi/chat` with tool-use.
```bash
python -m cli mcp test --skip-chat
```
Exits non-zero if any case fails.

### `voice`
Voice sub-app (STT/TTS on gate7; mic/speaker local). See
`cli/voice.py` / `cli/voice_io.py`.

```bash
python -m cli voice devices
python -m cli voice mic-test --seconds 3
python -m cli voice listen --transcribe
python -m cli voice speak "hello from the CLI"
python -m cli voice talk --once
```
`talk` runs a full voice loop: record → `/nexi/voice/transcribe` →
`/nexi/voice/chat` → play response audio. `--once` does a single turn.
