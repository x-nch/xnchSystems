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

---

## Soak Follow-up

### 2026-09-13 — DecisionLedger soak trace (Task 1, Gastown/Hermes integration)

- **Cron job:** `a2d6c649463c` (`xnch_health_probe`, `*/15 * * * *`)
- **Manual trigger:** `hermes cron run a2d6c649463c` → `Ran now: succeeded` (exit 0).
  ✅ Resolved 2026-09-13 (Task 3): direct `hermes cron run` from a fresh shell 401s unless
  `~/.xnch/hermes.env` is sourced **first** (`set -a; . ~/.xnch/hermes.env; set +a`). The pre-fix
  direct-run sessions `cron_a2d6c649463c_20260913_145840` / `_150154` executed `xnch_health` against the
  control plane but got `HTTP 401 invalid or missing MCP token` because the CLI-spawned MCP child does
  **not** inherit the daemon env (root cause is hermes `${XNCH_MCP_TOKEN}` interpolation, not the control
  plane). Env-sourced manual runs succeed — see the Task 3 sign-off below.
- **Natural builtin trace — marker (b) PASS:** execution `a6ab12ff26db4c49a9af3cb004a7ad51`
  (builtin, 15:00:58Z), session `cron_a2d6c649463c_20260913_150059`:
  `tool mcp__xmcp__xnch_health completed (0.04s, 2233 chars)` → health OK (status ok, redis ok,
  mcp_bridge.enabled=true, tool_count=76).
- **Marker (a) recall:** the `xnch_health_probe` prompt does not include a recall step, so no recall
  call appears in its natural trace. A one-shot hermes automation driven through the same xmcp bridge
  (15:06–15:07Z, env sourced) executed `xnch_memory_recall` (query "hermes health probe", top_k 2 → 0 results)
  then `xnch_health` (ok) in one turn — recall → tool-exec cycle confirmed end-to-end.
- **T2 403:** not observed in this window (optional; T1-tier denial for `xnch_memory_store_note` already
  verified 2026-09-12).
- **Status: PASS (with concerns)**
- **Concerns:**
  - Hermes daemon runs as a manual process (PID 1203, v0.21.2, `hermes gateway run --accept-hooks`), **not**
    under a systemd unit on node-b — no `hermes.service` present in `systemctl --user`.
  - 14:50:58 builtin run failed with `APIConnectionError` to vLLM `localhost:8082` (model mid-boot after the
    ~14:50 restart); all later runs OK.
  - Direct `hermes cron run` from a fresh shell 401s unless `~/.xnch/hermes.env` is sourced (see above).

**Control-plane ledger — verified directly (Fix round 1):**
- The gateway host is **node-a** (hostname `gate7`), dual-homed: `192.168.1.10` from the Mac, `192.168.50.1`
  from node-b. Route used: `ssh x-nch@node-a` (192.168.1.10) from this Mac — no jump needed.
- The nexi-pipeline `~/.xnch/audit/decisions.jsonl` on node-a has **no hermes entries** (stale since
  `2026-09-13T06:06:50`): it records only nexi decision-pipeline selections. The control-plane **automation
  trace lives in `~/.xnch/audit/events.jsonl`** (`TOOL_CALL` events with `trace_id`), which recorded every
  hermes run below.
- **Builtin prober run** (execution `a6ab12ff26db4c49a9af3cb004a7ad51`, session
  `cron_a2d6c649463c_20260913_150059`):
  `2026-09-13T15:01:02 TOOL_CALL xnch_health actor=hermes tier=T0_READ trace=5a3a3152-2e06-4bd6-9363-a59ffadf58cb`
- **One-shot recall→tool cycle** (15:07Z, env sourced):
  `2026-09-13T15:07:24 TOOL_CALL xnch_memory_recall actor=hermes tier=T0_READ trace=1520e40a-7fc1-46b5-94b7-0b4d29d79a73`
  `2026-09-13T15:07:25 TOOL_CALL xnch_health actor=hermes tier=T0_READ trace=5e111eb4-598f-43a8-8caa-7c5eea6387b1`
- Corroboration — the natural `*/15` tick keeps recording: `2026-09-13T15:16:03 TOOL_CALL xnch_health
  actor=hermes tier=T0_READ trace=d39b92a5-8ea1-4e5d-9516-077cf11733b9` (builtin run
  `03d4e2a25f6b491a842ef25d8c7c5581`, 15:15:59Z). Run→span mapping is by timestamp: events.jsonl entries
  carry trace_id but not session/run id; hermes-side `usage_audit.jsonl`/`agent.log` timestamps align exactly.
- 401 direct-run sessions (14:58:44 / 15:01:57) produce **no** events.jsonl entry — auth rejects before the
  TOOL_CALL event is emitted, consistent with round-1 root-cause (missing token interpolation).

### 2026-09-13 — Post-skills soak sign-off (Task 3, Gastown/Hermes integration)

**Soak follow-up: DONE ✅ (2026-09-13)** — cron trace verified end-to-end after skills generation + daemon
restart. Gates Phase C.

- **Manual cron trigger (post-skills, env sourced first):** `hermes cron run a2d6c649463c` →
  `Ran now: succeeded` (exit 0).
  - Run `84ececb454434b11a8056561b9bcda66` (source=direct, 15:33:55Z), session
    `cron_a2d6c649463c_20260913_153355`; `mcp__xmcp__xnch_health completed (0.04s, 2233 chars)` at 15:34:00 —
    no 401 (token present, env sourced).
- **Natural builtin tick (post-restart, skills dir live):** run `3748756c89174aa6ba4ba2be737701cf`
  (source=builtin, 15:30:05Z), session `cron_a2d6c649463c_20260913_153006`; xnch_health at 15:30:10
  (2233 chars). Both manual + builtin paths succeed with the skills config loaded.
- **Control-plane trace** (node-a `~/.xnch/audit/events.jsonl`, `TOOL_CALL`):
  - `2026-09-13T15:30:10 TOOL_CALL xnch_health actor=hermes tier=T0_READ trace=e6189eb1-a742-4a4e-b9d1-4dedeafacf83` ← builtin run `3748756c...`
  - `2026-09-13T15:34:00 TOOL_CALL xnch_health actor=hermes tier=T0_READ trace=b5239231-1940-47b5-8b0d-958aff2c760a` ← manual run `84ececb4...`
  - (Isolated `15:30:58` entry trace `949467bf-8b97-4be4-959c-c6b46977e372` has no matching cron session —
    gateway self-health/liveness call, consistent with the earlier 15:01:45 isolate; not a run.)
- **Skills check — SOFT finding:** `skills.external_dirs` = `/home/x-nch/.xnch/hermes-skills` (21
  `.skill.md` files) is loaded in the restarted daemon (PID 9029; config verified post-restart), but **no
  runtime evidence that the probe consumed a skill.** `xnch_health_probe` calls only `xnch_health`; hermes
  logs no skill load/usage lines (agent.log, journalctl, `~/.hermes/logs/` all clean), and `hermes skills
  list` enumerates only hub/builtin skills (53) — external-dir skills are not surfaced there, and `hermes
  skills config` is interactive-only. Nothing proves or refutes consumption; recorded as a **follow-up
  suggestion**, not a claim of proof (e.g., add a skill-triggering probe, or surface external-dir skill
  state/metrics in hermes logs).
- **Status: SOAK SIGN-OFF ✅ (2026-09-13)** — cron automation (manual + builtin) and control-plane trace
  verified post-skills. Soft finding above is non-blocking and recorded honestly.