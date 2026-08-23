# xnch agent-runner

Mac-side worker that claims tasks from xnch's dispatch queue and executes
them headless in opencode. Stdlib-only; no venv needed.

## Run manually
    cd agent-runner
    XNCH_GATEWAY_SECRET=<secret> python3 -m xnch_agent_runner

## Install as a service (launchd)
1. Fill placeholders in com.xnch.agent-runner.plist
   (REPO path, secret from web/.env.local, HOME).
2. cp com.xnch.agent-runner.plist ~/Library/LaunchAgents/
3. launchctl load ~/Library/LaunchAgents/com.xnch.agent-runner.plist
4. tail -f ~/xnch-agents/runner.log

## Env vars
| Var | Default | Meaning |
|---|---|---|
| XNCH_GATEWAY_URL | http://192.168.1.10:8001 | xnch gateway |
| XNCH_GATEWAY_SECRET | (required) | Hybrid-B shared secret |
| XNCH_RUNNER_ID | hostname | lease owner id |
| XNCH_AGENT_COMMAND | opencode | CLI to spawn |
| XNCH_AGENT_ARGS | run --agent xnch-dispatch | subcommand args (`--agent` REQUIRED unless XNCH_ALLOW_UNSCOPED_AGENT=1) |
| XNCH_ALLOW_UNSCOPED_AGENT | 0 | escape hatch: allow spawning without a pinned restricted agent |
| XNCH_RUNNER_TIMEOUT_S | 1800 | per-run subprocess timeout |
| XNCH_RUNNER_POLL_S | 5 | idle poll interval |

## Hardening (2026-08-24)
- Spawned agents receive an **allowlisted env only** (PATH/HOME/USER/… ) — never
  the launchd service environment or its secrets.
- Each workspace gets a project `opencode.json`: provider policy denies every
  LLM provider except `xnch-litellm` (local vLLM via LiteLLM), and loads the
  `opencode-sandbox` Seatbelt plugin for dispatched runs only.
- `OPENCODE_SANDBOX_CONFIG` injects strict deny-read (~/.ssh etc.) and a
  default-deny network allowlist for sandboxed bash.
- The pinned agent `xnch-dispatch` (in ~/.config/opencode/agents/) denies bash,
  MCP tools, external_directory; model pinned to local ornith.
