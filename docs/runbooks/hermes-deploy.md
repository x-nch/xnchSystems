# Hermes Agent — Deploy Runbook (node-b)

## Upstream install

Hermes Agent (Nous Research) — install per the [official Hermes docs](https://hermes-agent.org).

```bash
# Example install steps from upstream docs
curl -LsSf https://hermes-agent.org/install | sh
# or: pip install hermes-agent
# Then configure:
mkdir -p /home/x-nch/.xnch
```

## Environment setup

1. Create the env file with the MCP bridge credentials. Hermes cannot talk to the
   gateway's custom JSON `/mcp` router directly — its MCP client speaks the MCP
   protocol (stdio/streamable-HTTP). The transport is the **stdio bridge**
   `xnch_mcp/stdio_server.py` (run via `python -m xnch_mcp`), which forwards to
   the gateway HTTP `/mcp` endpoints. This env file is loaded into the daemon by
   the unit's `EnvironmentFile=` and referenced from the hermes `mcp_servers`
   config via `${VAR}` interpolation:

```bash
cat > /home/x-nch/.xnch/hermes.env <<'EOF'
XNCH_MCP_TOKEN=<your-mcp-token-here>
XNCH_ACTOR=hermes
XNCH_BASE_URL=http://192.168.50.1:8001
EOF
chown x-nch:x-nch /home/x-nch/.xnch/hermes.env
chmod 600 /home/x-nch/.xnch/hermes.env
```

- `XNCH_MCP_TOKEN` must match `XNCH_MCP_HTTP_TOKEN` on the xnch gateway (set in `xnch/config.py`).
- `XNCH_ACTOR=hermes` is sent as `X-Actor-Role: hermes` by the stdio bridge and
  signals the HTTP router to enforce T1-tier limits (only T0+T1 tools visible: 6).
- `XNCH_BASE_URL` is the gateway origin reachable from node-b (Tailscale).
- `X-Actor-Role` as a *header name* is obsolete — the stdio bridge maps
  `XNCH_ACTOR` → `X-Actor-Role` itself.

### Hermes-side MCP wiring (0.19.0)

1. Wrapper so the stdio server runs from the repo (module + `xnch.*` imports need
   the repo on `sys.path`; hermes passes no `cwd`):

```bash
mkdir -p /home/x-nch/.bin
cat > /home/x-nch/.bin/xnch-mcp.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
cd /home/x-nch/xnchSystems
exec ./.venv/bin/python -m xnch_mcp "$@"
EOF
chmod 755 /home/x-nch/.bin/xnch-mcp.sh
```

2. Register the server in `~/.hermes/config.yaml` (top-level key; hermes filters
   stdio env to the `env:` block + a safe baseline, so creds must be explicit):

```yaml
mcp_servers:
  xmcp:
    command: "/home/x-nch/.bin/xnch-mcp.sh"
    env:
      XNCH_BASE_URL: "http://192.168.50.1:8001"
      XNCH_ACTOR: "hermes"
      XNCH_MCP_TOKEN: "${XNCH_MCP_TOKEN}"
```

   `${XNCH_MCP_TOKEN}` is interpolated from the daemon's environment (the unit's
   `EnvironmentFile`) via hermes's `get_secret`. Validate with
   `hermes mcp test xmcp` (expect: Connected, 6 tools).

3. Model provider: no provider is configured upstream. Point hermes at node-b's
   local vLLM (`provider: "vllm"` with `base_url`) — hermes hard-requires a 64K
   context window, so set `context_length: 65536` (vLLM serves `max_model_len`
   32768; long sessions may hit the ceiling — raise `--max-model-len` upstream
   if VRAM allows).

2. (Optional) Install Python deps if using the Python helper:

```bash
cd /home/x-nch/xnchSystems
source .venv/bin/activate
pip install -e .
```

## Skills sync

Generate the SKILL.md files Hermes consumes via the `scripts/gen_agent_skills.py` generator from Task 2.3:

```bash
cd /home/x-nch/xnchSystems
python scripts/gen_agent_skills.py --out /home/x-nch/.xnch/hermes-skills
```

This reads the MCP registry and writes `{name}.skill.md` per tool with YAML front matter (name/description/tier) and input schema block. Hermes needs only T1-tier tools.

3. Verify generated skills:

```bash
ls /home/x-nch/.xnch/hermes-skills/
# All files should have .skill.md extension and valid YAML front matter
```

## systemd install

> **0.19.0 note**: `hermes agent --daemon` no longer exists. The resident process
> is `hermes gateway run` (foreground), which is also what drives the cron
> scheduler ("Gateway is not running — cron jobs will NOT fire"). The repo unit
> already reflects this, plus an `Environment=PATH=` override so `env hermes`
> resolves the binary outside the interactive shell's PATH.

1. Copy the unit file and enable:

```bash
sudo cp /home/xnch/xnchSystems/infra/no-k3s/node-b/systemd/hermes.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now hermes.service
```

2. Check service status:

```bash
systemctl is-active hermes.service    # expect: active
journalctl -u hermes.service -n 20 --no-pager
```

3. If the service fails, verify:

```bash
# Environment file is readable and has correct format
cat /home/x-nch/.xnch/hermes.env
# Check WorkingDirectory and User
```

## Soak checklist

After the service is running and skills are synced, run the following verification steps. All must pass before M3 can proceed.

| # | Check | Expected |
|---|-------|--------|
| 1 | **Tool visibility**: `GET /mcp/tools` with `X-Actor-Role: hermes` and `X-MCP-Token` headers → only ≤T1 tools visible | ✅ ≤T1 tools only; T2+ tools hidden |
| 2 | **Recall works**: automation runs `xnch_memory_recall` → returns results | ✅ Recall returns data |
| 3 | **Governed exec**: automation runs a T1 tool; a T2 attempt is denied (403) — verify in audit log | ✅ T1 succeeds; T2 returns 403; audit records the deny |
| 4 | **Durable write routed**: `am_memory_save` succeeds; `xnch_memory_store_note` from hermes → deprecation error (403) | ✅ `am_memory_save` OK; `xnch_memory_store_note` returns 403 with deprecation message |
| 5 | **One full automation end-to-end** appears in the DecisionLedger | ✅ Single automation trace from start → finish in `~/.xnch/audit/decisions.jsonl` |

### Soak checklist detail

1. **Tool visibility**: Trigger a `GET /mcp/tools` request with hermes headers and confirm only T1-tier (or lower) tools appear in the response.

2. **Recall works**: Run `xnch_memory_recall` through Hermes — the episodic memory query should return results.

3. **Governed exec**: Have Hermes execute a T1 MCP tool (e.g., via the bridge). Then attempt a T2-tier tool — it must be rejected with HTTP 403. Confirm the audit log records the denial.

4. **Durable write routing**: Call `am_memory_save` (agentmemory bridged tool) — it should succeed. Then call the deprecated `xnch_memory_store_note` from Hermes — it must return HTTP 403 with the deprecation message confirming the new routing policy is active.

5. **DecisionLedger**: Run one complete automation cycle (recall → tool exec → HITL approval if applicable). Check `~/.xnch/audit/decisions.jsonl` — there should be a new entry tracing the full automation.

## Rollback

```bash
sudo systemctl stop hermes.service
sudo systemctl disable hermes.service
rm /etc/systemd/system/hermes.service
sudo systemctl daemon-reload
```

---

**Reference:** Unit file at `infra/no-k3s/node-b/systemd/hermes.service`.