# Gate 1 — Phase 1: node-b Capability-Sidecar Cutover Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cutover from two legacy sidecar processes (`exec-agent` :8004 + `fs-read-agent` :8003) to the merged `xnch-capability` sidecar (:8090) on node-b, flip the xnch gateway to target it, verify, and decommission the old processes.

**Architecture:** The merged `capability_agent` FastAPI app (already landed — commits `7804533` through `b1ccf29`) serves governed-exec and read-only-fs on `:8090` with one shared bearer token. The `xnch` gateway dispatch chain (`ExecRunService.from_settings` / `FsReadService.from_settings`) prefers `XNCH_CAPABILITY_NODE_B_URL` + `XNCH_CAPABILITY_TOKEN`, falling back to the legacy `XNCH_EXEC_AGENT_NODE_B_URL` / `XNCH_FS_AGENT_NODE_B_URL`. The cutover is a single env-var flip with instant rollback via unset + restart.

**Tech Stack:** FastAPI (`capability_agent`), Python `httpx` (remote clients), systemd (xnch-capability.service), Pydantic BaseSettings (`xnch/config.py`).

**Spec:** `docs/superpowers/specs/2026-09-11-micro-component-split.md`
**Plan:** `docs/superpowers/plans/2026-09-11-phase1-capability-consolidation.md` (Tasks 1–7; this runbook executes Tasks 6–7)

---

## File Structure

| File | Role |
|------|------|
| `/home/x-nch/.xnch/nexi.env` (node-b) | Read `XNCH_EXEC_AGENT_TOKEN`; append `XNCH_CAPABILITY_TOKEN` |
| `infra/no-k3s/node-b/systemd/xnch-capability.service` | systemd unit (already in repo, to be deployed to node-b) |
| `infra/no-k3s/node-b/systemd/exec-agent.service` | Legacy unit (to disable) |
| `infra/no-k3s/node-b/systemd/fs-read-agent.service` | Legacy unit (to disable) |
| `/home/x-nch/.xnch/xnch.env` (node-a/gateway) | Append `XNCH_CAPABILITY_NODE_B_URL` + `XNCH_CAPABILITY_TOKEN` |
| `/home/x-nch/.xnch/exec-policy.yaml` (both nodes) | Deploy updated shared policy (`infra/no-k3s/shared/exec-policy.yaml`) |

---

## Global Constraints

- Node-b IP: `192.168.50.2`; gateway (node-a/gate7) IP: `192.168.50.1`.
- Venv on node-b: `/home/x-nch/xnchSystems/nexi/.venv/bin/python`.
- Venv on node-a: `/home/x-nch/xnchSystems/xnch/.venv/bin/python`.
- `XNCH_CAPABILITY_TOKEN` = same value as existing `XNCH_EXEC_AGENT_TOKEN` in `nexi.env`.
- Capability agent binds `0.0.0.0:8090` (set in systemd unit; the unit is already in the repo at `infra/no-k3s/node-b/systemd/xnch-capability.service`).
- `cli mcp test --skip-chat` exercises bridge/CRG/AM/doc/web-search health — **not** exec/fs tools. Sidecar reachability must be verified separately via `curl`.
- All commands below run from the repo root (`/home/x-nch/xnchSystems`) on the target host.

---

## Task A: Bring up merged sidecar on node-b (:8090)

**Host:** node-b (`192.168.50.2`)
**Precondition:** Port 8090 is free. `ss -ltn | grep 8090` → empty.

- [ ] **Step 1: Verify port 8090 is free**

```bash
ss -ltn | grep 8090
# Expected: empty (no output)
```

- [ ] **Step 2: Set XNCH_CAPABILITY_TOKEN in nexi.env**

Extract the existing exec-agent token and append it as the new capability token:

```bash
grep XNCH_EXEC_AGENT_TOKEN /home/x-nch/.xnch/nexi.env
# Confirm non-empty — shows: XNCH_EXEC_AGENT_TOKEN=<value>

# Append capability token (same value)
EXTRACTED=$(grep XNCH_EXEC_AGENT_TOKEN /home/x-nch/.xnch/nexi.env | cut -d= -f2)
echo "XNCH_CAPABILITY_TOKEN=$EXTRACTED" >> /home/x-nch/.xnch/nexi.env
grep XNCH_CAPABILITY_TOKEN /home/x-nch/.xnch/nexi.env
# Expected: XNCH_CAPABILITY_TOKEN=<same value>
```

- [ ] **Step 3: Install and start xnch-capability.service**

```bash
sudo cp infra/no-k3s/node-b/systemd/xnch-capability.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now xnch-capability
```

- [ ] **Step 4: Verify sidecar health**

```bash
curl -s http://127.0.0.1:8090/health
# Expected: {"status":"ok","capabilities":"exec,fs"}

systemctl is-active xnch-capability
# Expected: active
```

- [ ] **Step 5: Verify exec endpoint on sidecar (token + policy)**

`echo` is NOT allowlisted in `exec-policy.yaml` — use `hostname` (allowlisted for node-b):

```bash
TOKEN=$(grep XNCH_CAPABILITY_TOKEN /home/x-nch/.xnch/nexi.env | cut -d= -f2)
curl -s -w '\nHTTP %{http_code}\n' -X POST http://127.0.0.1:8090/exec/run \
  -H "X-Internal-Token: $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"command":"hostname"}'
# Expected: HTTP 200, result.stdout is node-b's hostname (non-empty)
```

- [ ] **Step 6: Verify fs endpoint on sidecar**

`/fs/read` is a GET endpoint; paths are relative to `~/.xnch/fs-policy.yaml` roots on node-b (use the `xnchSystems/...` prefix for repo files).

```bash
curl -s -w '\nHTTP %{http_code}\n' -G http://127.0.0.1:8090/fs/read \
  -H "X-Internal-Token: $TOKEN" \
  --data-urlencode "path=xnchSystems/nexi/main.py" \
  --data-urlencode "max_bytes=100"
# Expected: HTTP 200, body contains file content (or at least a non-error JSON)
```

**Gate A:** Sidecar returns `{"status":"ok","capabilities":"exec,fs"}`; exec and fs endpoints return HTTP 200 with valid payloads. Only then proceed to Task B.

**Rollback A:** (nothing to roll back — legacy sidecars are still running; new unit just sits alongside)

---

## Task B: Flip gateway callers on node-a to target capability sidecar

**Host:** node-a / gate7 (`192.168.50.1`)
**Precondition:** Task A passed (sidecar healthy on node-b :8090).

- [ ] **Step 1: Append capability env vars to xnch.env**

```bash
# Confirm current legacy vars exist (informational)
grep XNCH_EXEC_AGENT_NODE_B_URL /home/x-nch/.xnch/xnch.env
grep XNCH_FS_AGENT_NODE_B_URL /home/x-nch/.xnch/xnch.env
# Both should show defaults (the fallback chain if capability URL is unset)

# The token value is the same as the legacy XNCH_EXEC_AGENT_TOKEN already
# present in node-a's xnch.env (== XNCH_CAPABILITY_TOKEN set on node-b)
TOKEN=$(grep XNCH_EXEC_AGENT_TOKEN /home/x-nch/.xnch/xnch.env | cut -d= -f2)
[ -n "$TOKEN" ] || echo "ERROR: XNCH_EXEC_AGENT_TOKEN not found in xnch.env"

# Append new vars
cat >> /home/x-nch/.xnch/xnch.env <<EOF
XNCH_CAPABILITY_NODE_B_URL=http://192.168.50.2:8090
XNCH_CAPABILITY_TOKEN=$TOKEN
EOF

# Verify
grep XNCH_CAPABILITY /home/x-nch/.xnch/xnch.env
# Expected:
# XNCH_CAPABILITY_NODE_B_URL=http://192.168.50.2:8090
# XNCH_CAPABILITY_TOKEN=<value>
```

- [ ] **Step 2: Restart xnch gateway**

```bash
sudo systemctl restart xnch
systemctl is-active xnch
# Expected: active
```

- [ ] **Step 3: Verify gateway health (regression check)**

```bash
cd /home/x-nch/xnchSystems
/home/x-nch/xnchSystems/xnch/.venv/bin/python -m cli mcp test --skip-chat
# Expected: all 11 cases PASS (this confirms bridge health is not regressed)
```

- [ ] **Step 4: Verify exec tool via gateway → sidecar (end-to-end)**

Uses `hostname` (allowlisted for node-b in `exec-policy.yaml`):

```bash
curl -s -w '\nHTTP %{http_code}\n' -X POST http://127.0.0.1:8001/mcp/call \
  -H 'X-Actor-Role: nexi' -H 'Content-Type: application/json' \
  -d '{"name":"xnch_exec_run","arguments":{"host":"node-b","command":"hostname"}}'
# Expected: HTTP 200, result.stdout is node-b's hostname (non-empty)
```

- [ ] **Step 5: Verify fs tool via gateway → sidecar (end-to-end)**

```bash
curl -s -w '\nHTTP %{http_code}\n' -X POST http://127.0.0.1:8001/mcp/call \
  -H 'X-Actor-Role: nexi' -H 'Content-Type: application/json' \
  -d '{"name":"xnch_fs_read","arguments":{"host":"node-b","path":"xnchSystems/nexi/main.py","max_bytes":100}}'
# Expected: HTTP 200, result contains file content (non-error JSON)
```

- [ ] **Step 6: Verify fallback path (optional — sanity check)**

Temporarily unset the capability URL to confirm legacy still works (dual-run):

```bash
grep -v "^XNCH_CAPABILITY_NODE_B_URL=" /home/x-nch/.xnch/xnch.env > /tmp/xnch.env.bak
sudo cp /tmp/xnch.env.bak /home/x-nch/.xnch/xnch.env
sudo systemctl restart xnch
curl -s -X POST http://127.0.0.1:8001/mcp/call \
  -H 'X-Actor-Role: nexi' -H 'Content-Type: application/json' \
  -d '{"name":"xnch_exec_run","arguments":{"host":"node-b","command":"hostname"}}'
# Expected: HTTP 200 — confirms legacy paths still work before decommission

# Restore capability URL (the token line is still present — only URL was
# removed above) and restart
cat >> /home/x-nch/.xnch/xnch.env <<EOF
XNCH_CAPABILITY_NODE_B_URL=http://192.168.50.2:8090
EOF
sudo systemctl restart xnch
```

**Gate B:** `python -m cli mcp test --skip-chat` all green; exec + fs curls return HTTP 200 with valid data via the new sidecar path. Fallback path confirmed working. Only then proceed to Task C.

**Rollback B (if any step fails before Gate B):**

```bash
# On node-a: remove capability env vars
grep -v "^XNCH_CAPABILITY_NODE_B_URL=\|^XNCH_CAPABILITY_TOKEN=" /home/x-nch/.xnch/xnch.env > /tmp/xnch.env.clean
sudo cp /tmp/xnch.env.clean /home/x-nch/.xnch/xnch.env
sudo systemctl restart xnch
# Clients fall back to legacy XNCH_EXEC_AGENT_NODE_B_URL / XNCH_FS_AGENT_NODE_B_URL
# Legacy sidecars (:8004, :8003) are still running — no further action needed
```

---

## Task C: Decommission legacy sidecars on node-b

**Host:** node-b (`192.168.50.2`)
**Precondition:** Gate B passed. Gateway confirmed routing to :8090 for exec and fs.

- [ ] **Step 1: Stop legacy units**

```bash
sudo systemctl disable --now exec-agent fs-read-agent
systemctl is-active exec-agent
# Expected: inactive
systemctl is-active fs-read-agent
# Expected: inactive
```

- [ ] **Step 2: Confirm capability sidecar still healthy after legacy stop**

```bash
curl -s http://127.0.0.1:8090/health
# Expected: {"status":"ok","capabilities":"exec,fs"}

# End-to-end re-check (from node-a or directly):
TOKEN=$(grep XNCH_CAPABILITY_TOKEN /home/x-nch/.xnch/nexi.env | cut -d= -f2)
curl -s -w '\nHTTP %{http_code}\n' -X POST http://127.0.0.1:8090/exec/run \
  -H "X-Internal-Token: $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"command":"hostname"}'
# Expected: HTTP 200
```

- [ ] **Step 3: Update exec-policy.yaml — clean up legacy entries**

In the shared policy file `infra/no-k3s/shared/exec-policy.yaml`:

1. **node-a section:** Remove the duplicate `curl http://192.168.50.2:8090` entry (lines 69–70 are identical; keep only one).
2. **node-b section:** Remove `curl http://127.0.0.1:8004` (line 140 — legacy exec-agent port; `:8090` is already present on line 139).

```bash
# Quick confirmation of current state before editing:
grep -n "8003\|8004\|8090" infra/no-k3s/shared/exec-policy.yaml
# Expected after cleanup:
#   node-a section: curl http://192.168.50.2:8090  (once)
#   node-b section: curl http://127.0.0.1:8090     (once)
#   No :8003 or :8004 entries remain
```

Use `edit` to make the changes in `infra/no-k3s/shared/exec-policy.yaml`:
- Remove one of the two duplicate `curl http://192.168.50.2:8090` lines in the node-a `allowed_prefixes` section.
- Remove `curl http://127.0.0.1:8004` from the node-b `allowed_prefixes` section.

- [ ] **Step 4: Deploy updated policy to both nodes**

```bash
# node-a:
cp infra/no-k3s/shared/exec-policy.yaml ~/.xnch/exec-policy.yaml
sudo systemctl restart xnch

# node-b (over SSH or directly):
ssh x-nch@192.168.50.2 "cp /home/x-nch/xnchSystems/infra/no-k3s/shared/exec-policy.yaml /home/x-nch/.xnch/exec-policy.yaml && sudo systemctl restart xnch-capability"
```

- [ ] **Step 5: Final regression suite (from node-a)**

```bash
cd /home/x-nch/xnchSystems
/home/x-nch/xnchSystems/xnch/.venv/bin/python -m cli mcp test --skip-chat
# Expected: all 11 cases PASS

# End-to-end exec + fs (same as Task B steps 4–5 — confirm still working after policy reload)
curl -s -X POST http://127.0.0.1:8001/mcp/call \
  -H 'X-Actor-Role: nexi' -H 'Content-Type: application/json' \
  -d '{"name":"xnch_exec_run","arguments":{"host":"node-b","command":"hostname"}}'
curl -s -X POST http://127.0.0.1:8001/mcp/call \
  -H 'X-Actor-Role: nexi' -H 'Content-Type: application/json' \
  -d '{"name":"xnch_fs_read","arguments":{"host":"node-b","path":"xnchSystems/nexi/main.py","max_bytes":100}}'
# Both expected: HTTP 200
```

**Gate C:** Legacy units `inactive` + all verification curls pass + `cli mcp test` green. The cutover is complete.

**Rollback C (if decommission caused issues):**

```bash
# On node-b: re-enable legacy units
sudo systemctl enable --now exec-agent fs-read-agent
systemctl is-active exec-agent
# Expected: active

# On node-a: the capability env vars still point to :8090 (still healthy)
# No change needed — both paths coexist; gateway routes to capability sidecar
# If you want to fully roll back, follow the Rollback D procedure below
```

---

## Task D: Full Rollback (emergency)

Use if the gateway can no longer reach the capability sidecar after any step. Restores pre-cutover state.

**Host:** node-a (primary action) + node-b (restore legacy)

- [ ] **Step 1: On node-a — remove capability env vars and restart**

```bash
grep -v "^XNCH_CAPABILITY_NODE_B_URL=\|^XNCH_CAPABILITY_TOKEN=" /home/x-nch/.xnch/xnch.env > /tmp/xnch.env.rollback
sudo cp /tmp/xnch.env.rollback /home/x-nch/.xnch/xnch.env
sudo systemctl restart xnch
```

Clients fall back to `XNCH_EXEC_AGENT_NODE_B_URL` (`:8004`) and `XNCH_FS_AGENT_NODE_B_URL` (`:8003`).

- [ ] **Step 2: On node-b — re-enable legacy units**

```bash
sudo systemctl enable --now exec-agent fs-read-agent
systemctl is-active exec-agent fs-read-agent
# Expected: both active
```

- [ ] **Step 3: Verify legacy path works (from node-a)**

```bash
curl -s -X POST http://127.0.0.1:8001/mcp/call \
  -H 'X-Actor-Role: nexi' -H 'Content-Type: application/json' \
  -d '{"name":"xnch_exec_run","arguments":{"host":"node-b","command":"hostname"}}'
# Expected: HTTP 200
```

- [ ] **Step 4: (Optional) Keep capability sidecar running for dual-run**

The `xnch-capability` unit may remain running for future re-attempt. To fully revert:

```bash
# node-b:
sudo systemctl disable --now xnch-capability
# node-a: XNCH_CAPABILITY_NODE_B_URL already removed (Step 1)
```

---

## Post-Cutover Cleanup (follow-up, not part of this gate)

After confirming stability for ≥24 hours:
- Delete `exec_agent/` and `fs_read_agent/` packages from the repo (Task 7 of phase-1 plan).
- Remove `XNCH_EXEC_AGENT_NODE_B_URL`, `XNCH_FS_AGENT_NODE_B_URL`, `XNCH_EXEC_AGENT_TOKEN`, `XNCH_FS_AGENT_TOKEN` from env files (once no rollback is expected).
- Commit policy cleanup to `infra/no-k3s/shared/exec-policy.yaml`.
