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
| XNCH_AGENT_ARGS | run | subcommand args |
| XNCH_RUNNER_TIMEOUT_S | 1800 | per-run subprocess timeout |
| XNCH_RUNNER_POLL_S | 5 | idle poll interval |
