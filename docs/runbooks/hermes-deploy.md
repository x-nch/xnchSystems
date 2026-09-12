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

1. Create the env file with MCP bridge credentials:

```bash
cat > /home/x-nch/.xnch/hermes.env <<'EOF'
XNCH_MCP_TOKEN=<your-mcp-token-here>
X-Actor-Role=hermes
EOF
chown x-nch:x-nch /home/x-nch/.xnch/hermes.env
chmod 600 /home/x-nch/.xnch/hermes.env
```

- `XNCH_MCP_TOKEN` must match `XNCH_MCP_HTTP_TOKEN` on the xnch gateway (set in `xnch/config.py`).
- `X-Actor-Role: hermes` signals the HTTP router to enforce T1-tier limits.

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