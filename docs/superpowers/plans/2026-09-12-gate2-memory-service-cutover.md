# Gate 2 — Phase 2: Memory-Service Cutover Plan (node-a)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Start the extracted `xnch-memory` service on node-a `:8003`, flip the xnch gateway to remote stores (`XNCH_MEMORY_EMBEDDED=false`), verify recall/store/SSE-replay/chat, retarget consolidation, and establish the instant rollback path.

**Architecture:** The memory-service (`python -m xnch.memory.server` on the nexi venv) owns PostgreSQL/Redis/Kuzu stores directly. The gateway's `build_memory()` in `xnch/memory/bootstrap.py` selects embedded (in-process stores, `XNCH_MEMORY_EMBEDDED=true`, the default) or remote (`RemoteStoreRef`/`RemoteGraphStore`/`DegradingEpisodic` HTTP refs). The cutover is a single env-var flip with instant rollback. Exactly ONE process may own `~/.xnch/graph.kuzu` at any time: embedded gateway XOR memory-service.

**Tech Stack:** FastAPI (memory-service), Pydantic BaseSettings (`xnch/config.py`), httpx (remote clients), Kuzu (`~/.xnch/graph.kuzu`), PostgreSQL, Redis, systemd.

**Spec:** `docs/superpowers/specs/2026-09-11-micro-component-split.md` (T2.5, T2.6)
**Plan:** `docs/superpowers/plans/2026-09-11-phase2-memory-service-extraction.md` (Task 9 Step 7 = USER OPS GATE)
**Runbook:** `docs/runbooks/memory-service-deploy.md` (this gate executes + verifies it)

---

## File Structure

| File | Role |
|------|------|
| `infra/no-k3s/node-a/systemd/xnch-memory.service` | systemd unit for the memory-service (port 8003, nexi venv) |
| `infra/no-k3s/node-a/systemd/consolidation.service` | retargeted unit: POSTs `:8003/v1/consolidation/run` (needs re-install on node-a) |
| `~/.xnch/xnch.env` (node-a) | env both units read: `XNCH_MEMORY_TOKEN`, `XNCH_MEMORY_EMBEDDED`, `XNCH_MEMORY_SERVICE_URL` |
| `~/.xnch/graph.kuzu` (node-a) | Kuzu DB dir — exactly ONE owner at a time |
| `xnch/` git submodule | source of the Phase 2 code (`memory/server.py`, `client.py`, `bootstrap.py`, SSE relay) |

---

## Global Constraints

- Gateway host = node-a / gate7 (`192.168.50.1`), login as `x-nch`; systemd commands need `sudo`.
- All file paths in commands are the **node-a** paths (`/home/x-nch/...`), even when the command looks like a repo path (`infra/no-k3s/node-a/systemd/...` = `~/xnchSystems/infra/no-k3s/node-a/systemd/...`).
- Gateway venv python: `/home/x-nch/xnchSystems/xnch/.venv/bin/python`.
- Memory-service venv python: `/home/x-nch/xnchSystems/nexi/.venv/bin/python` (PYTHONPATH set by the unit).
- Kuzu DB dir: `~/.xnch/graph.kuzu` (derived from `XNCH_BASE_DIR` default `~/.xnch`). Owner check via `lsof ~/.xnch/graph.kuzu` (one `python` PID expected).
- `XNCH_MEMORY_TOKEN` **must** be set in `~/.xnch/xnch.env` before `xnch-memory` starts — the service is fail-closed (unset token ⇒ 503, never 401/200).
- `XNCH_MEMORY_EMBEDDED` defaults to `true`; the (absent) `XNCH_LANGGRAPH_PIPELINE` gate means the LangGraph pipeline is skipped in remote mode (accepted — see runbook Preconditions).
- Kuzu single-owner ordering: **stop the embedded gateway BEFORE starting `xnch-memory`** (see Task B note). A second process opening an in-use Kuzu DB fails its `GraphStore.connect()` and the service crash-loops (RestartSec=10). Service-first is only safe if the gateway is already stopped or already in remote mode.
- Deviations from the literal runbook command order are deliberate (Kuzu safety); rollout + rollback are symmetric: the releasing side stops first.

---

## Task 0: Publish Phase 2 code (dev workspace — this Mac, GitHub)

**Host:** local dev checkout (this repo). **Blocking gate for everything after.**

Phase 2 lives in the `xnch` submodule at `1a46511` but is NOT published: origin `xnch@master` is `0b80c07` and the superrepo gitlink still pins `0b80c07`. node-a's `git submodule update --force` would checkout a tree WITHOUT `memory/server.py`. Publish first.

- [ ] **Step 1: Confirm xnch submodule is clean and on master at the phase-2 HEAD**

```bash
git -C xnch status --porcelain          # expect: empty
git -C xnch rev-parse master            # expect: 1a465111a9ac36530ed5c5978f7275c07a356050 (or the phase-2 HEAD)
```

- [ ] **Step 2: Push xnch master (OPS GATE — explicit confirmation will be requested before pushing)**

```bash
git -C xnch push origin master
git -C xnch ls-remote origin master     # expect: 1a465111... refs/heads/master
```

- [ ] **Step 3: Bump the superrepo gitlink and push**

```bash
git add xnch
git commit -m "chore(xnch): bump submodule to phase-2 memory-service HEAD"
git push origin master
git ls-tree HEAD xnch | awk '{print $3}'   # expect: 1a465111...
```

**Gate 0:** `xnch` origin master and the superrepo gitlink both resolve to `1a46511*`.

---

## Task A: Preconditions + state snapshot (node-a)

**Host:** node-a (`192.168.50.1`). Run from `/home/x-nch/xnchSystems`.

- [ ] **Step 1: Confirm Phase 2 code is deployed on node-a**

```bash
git -C ~/xnchSystems rev-parse HEAD
git -C ~/xnchSystems ls-tree HEAD xnch | awk '{print $3}'    # expect: 1a46511... (or newer)
git -C ~/xnchSystems submodule update --init --recursive --force
test -f ~/xnchSystems/xnch/memory/server.py && echo "server.py present"
test -f ~/xnchSystems/xnch/memory/bootstrap.py && echo "bootstrap.py present"
```

If the gitlink is not `1a46511*`, deploy the published master:

```bash
git -C ~/xnchSystems fetch origin master
git -C ~/xnchSystems checkout -f master
git -C ~/xnchSystems submodule update --init --recursive --force
```

- [ ] **Step 2: Smoke-import the service under the unit's python + PYTHONPATH**

```bash
PYTHONPATH=/home/x-nch/xnchSystems:/home/x-nch/xnchSystems/xnch \
  /home/x-nch/xnchSystems/nexi/.venv/bin/python -c \
  "import xnch.memory.server, xnch.memory.bootstrap, scraper.pipeline.store; print('imports ok')"
# Expected: imports ok
```

(Import smoke catches a missing `scraper` dep in the nexi venv before systemd flips. If it fails, `uv pip install --python ~/xnchSystems/nexi/.venv/bin/python -e ~/xnchSystems/xnch` and retry.)

- [ ] **Step 3: Snapshot current service state**

```bash
ss -ltn | grep 8003                    # expect: empty — port must be free
systemctl is-active xnch               # expect: active, inactive, or failed — record which
systemctl is-active xnch-memory        # expect: inactive (unit not yet installed)
grep -E '^XNCH_MEMORY_(TOKEN|EMBEDDED|SERVICE_URL)=' ~/.xnch/xnch.env || echo "no XNCH_MEMORY_* set yet"
grep -E '^XNCH_LANGGRAPH_PIPELINE=' ~/.xnch/xnch.env || echo "langgraph_pipeline unset (skipped in remote mode — OK)"
lsof ~/.xnch/graph.kuzu                # which PID owns Kuzu today?
```

**Gate A:** imports ok; port 8003 free; `XNCH_MEMORY_TOKEN` set (if absent, go to Task B Step 1 first). Record the snapshot (service states + Kuzu owner) — it is the rollback reference.

---

## Task B: Bring up the memory-service on node-a (:8003)

**Host:** node-a. **Ordering note (Kuzu safety):** if `systemctl is-active xnch` shows the gateway running in embedded mode, it currently holds `~/.xnch/graph.kuzu`. Stop it FIRST so the memory-service is the sole Kuzu owner. This deviates from the runbook's service-first order deliberately — service-first would only work if the gateway is already stopped or already remote.

- [ ] **Step 1: Ensure XNCH_MEMORY_TOKEN is set (generate if absent)**

```bash
grep -q '^XNCH_MEMORY_TOKEN=' ~/.xnch/xnch.env || {
  TOK=$(head -c 32 /dev/urandom | base64 | tr -d '=+/')
  printf 'XNCH_MEMORY_TOKEN=%s\n' "$TOK" >> ~/.xnch/xnch.env
}
grep '^XNCH_MEMORY_TOKEN=' ~/.xnch/xnch.env
# Expected: XNCH_MEMORY_TOKEN=<non-empty value>. SAVE this value.
```

- [ ] **Step 2: Stop the gateway (release Kuzu) if it is running**

```bash
if systemctl is-active --quiet xnch; then
  sudo systemctl stop xnch
  systemctl is-active xnch        # expect: inactive
fi
sleep 2
lsof ~/.xnch/graph.kuzu || echo "Kuzu not held by any process — safe to start memory-service"
```

- [ ] **Step 3: Install and start xnch-memory.service**

```bash
sudo cp ~/xnchSystems/infra/no-k3s/node-a/systemd/xnch-memory.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now xnch-memory
systemctl is-active xnch-memory    # expect: active
```

- [ ] **Step 4: Verify memory-service health (all tiers up)**

```bash
TOKEN=$(grep '^XNCH_MEMORY_TOKEN=' ~/.xnch/xnch.env | tail -1 | cut -d= -f2-)
curl -s -H "X-Internal-Token: $TOKEN" http://127.0.0.1:8003/healthz
# Expected: {"status":"ok","tiers":{"postgres":true,"kuzu":true}}
```

If `tiers.kuzu=false` or `status:degraded`: `journalctl -u xnch-memory -n 40 --no-pager` — a Kuzu lock error means the gateway still held the DB (didn't release in Step 2); stop both, restart memory-service. A `503` means the token in the unit's EnvironmentFile isn't the one the process loaded (recheck Step 1).

**Gate B:** `xnch-memory` active; healthz returns `{"status":"ok","tiers":{"postgres":true,"kuzu":true}}`; `lsof ~/.xnch/graph.kuzu` shows exactly one (memory-service) PID.

---

## Task C: Flip the gateway to remote stores

**Host:** node-a.

- [ ] **Step 1: Set the remote-mode env vars in ~/.xnch/xnch.env**

```bash
grep -q '^XNCH_MEMORY_EMBEDDED=' ~/.xnch/xnch.env \
  && sed -i 's/^XNCH_MEMORY_EMBEDDED=.*/XNCH_MEMORY_EMBEDDED=false/' ~/.xnch/xnch.env \
  || printf 'XNCH_MEMORY_EMBEDDED=false\n' >> ~/.xnch/xnch.env
grep -q '^XNCH_MEMORY_SERVICE_URL=' ~/.xnch/xnch.env \
  && sed -i 's|^XNCH_MEMORY_SERVICE_URL=.*|XNCH_MEMORY_SERVICE_URL=http://127.0.0.1:8003|' ~/.xnch/xnch.env \
  || printf 'XNCH_MEMORY_SERVICE_URL=http://127.0.0.1:8003\n' >> ~/.xnch/xnch.env
grep -E '^XNCH_MEMORY_(EMBEDDED|SERVICE_URL|TOKEN)=' ~/.xnch/xnch.env
# Expected:
#   XNCH_MEMORY_EMBEDDED=false
#   XNCH_MEMORY_SERVICE_URL=http://127.0.0.1:8003
#   XNCH_MEMORY_TOKEN=<same value as Task B Step 1>
```

- [ ] **Step 2: Start the gateway with the remote config**

```bash
sudo systemctl start xnch
systemctl is-active xnch          # expect: active
sleep 3
curl -s http://127.0.0.1:8001/health
# Expected: {"status":"ok","redis":"ok",...} — gateway up
```

- [ ] **Step 3: Confirm single-owner invariant holds (the decisive remote-mode check)**

```bash
lsof ~/.xnch/graph.kuzu
# Expected: exactly ONE process — the xnch-memory service PID. NO gateway (uvicorn) PID.
ss -ltn | grep 8001               # gateway listener
ss -ltn | grep 8003               # memory-service listener
```

If the gateway PID appears in `lsof ~/.xnch/graph.kuzu`, the closure of `s.memory` (main.py:273 `await s.memory.aclose()`) did not release the graph — the env flip did not take (recheck `XNCH_MEMORY_EMBEDDED=false` is actually in the file the unit reads; `systemctl show xnch -p EnvironmentFile`).

**Gate C:** gateway active + `/health` ok; Kuzu held ONLY by `xnch-memory`; both listeners up.

---

## Task D: Verify remote stores through the gateway

**Host:** node-a. Every check below must round-trip gateway → memory-service over HTTP.

- [ ] **Step 1: Kuzu path via gateway (graph stats)**

```bash
curl -s http://127.0.0.1:8001/memory/graph/stats
# Expected: JSON with entity_count / relation_count / types — proves RemoteGraphStore → /v1/call → Kuzu
```

- [ ] **Step 2: Recall path via gateway (episodic manifest)**

```bash
curl -s -X POST http://127.0.0.1:8001/memory/read \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"gate2-verify","actor_id":"gate2","actor_role":"operator","query":{}}'
# Expected: manifest with episodes/patterns/experiences arrays — proves DegradingEpisodic → pg_episodic over HTTP
```

- [ ] **Step 3: Canned bridge suite (recall + store tools)**

```bash
cd /home/x-nch/xnchSystems
/home/x-nch/xnchSystems/xnch/.venv/bin/python -m cli mcp test --skip-chat
# Expected: all 11 tool-level cases PASS
```

- [ ] **Step 4: SSE relay on the gateway**

```bash
TOKEN=$(grep '^XNCH_MEMORY_TOKEN=' ~/.xnch/xnch.env | tail -1 | cut -d= -f2-)
# direct service stream (baseline)
curl -s -N --max-time 4 -H "X-Internal-Token: $TOKEN" http://127.0.0.1:8003/v1/graph/stream \
  | head -4
# gateway relay (:8001 → :8003)
curl -s -N --max-time 4 http://127.0.0.1:8001/memory/graph/stream | head -4
# Expected (both): events of type stats / ready / heartbeat
```

- [ ] **Step 5: Consolidation fires through the service**

Re-install the retargeted unit (the installed copy still points at the old gateway `:8001/admin/consolidate`):

```bash
grep -q 8003 /etc/systemd/system/consolidation.service || {
  sudo cp ~/xnchSystems/infra/no-k3s/node-a/systemd/consolidation.service /etc/systemd/system/
  sudo systemctl daemon-reload
}
grep ExecStart /etc/systemd/system/consolidation.service    # expect: ... 8003/v1/consolidation/run
sudo systemctl start consolidation.service
sleep 3
journalctl -u xnch-memory --since "2 minutes ago" --no-pager | grep -i "consolidation\|POST"
# Expected: POST /v1/consolidation/run → 200
systemctl show consolidation.timer -p NextElapseOnCalendar   # expect: next 02:00 fire
```

- [ ] **Step 6: Chat + web UI**

```bash
# live tool-loop chat cases (needs LiteLLM reachable); otherwise verify in muse UI
/home/x-nch/xnchSystems/xnch/.venv/bin/python -m cli mcp test
```

If the toolbar cases need LLM access, verify manually in the web UI: open the chat, ask a recall-bearing question, confirm the graph page streams on `/memory/graph/stream`.

**Gate D:** graph stats + memory/read return real data via the relay; `mcp test --skip-chat` green; SSE relay streams; consolidation returns 200 against `xnch-memory`; chat works.

---

## Task E: Rollback (instant) + rehearsal

**Host:** node-a. One-command rollback is the safety net; rehearse it once, then **end back in remote mode** (the intended end state).

Full rollback (embedded gateway reclaims Kuzu — stop the service FIRST so only the gateway owns the DB):

```bash
sudo systemctl stop xnch-memory
sed -i 's/^XNCH_MEMORY_EMBEDDED=false/XNCH_MEMORY_EMBEDDED=true/' ~/.xnch/xnch.env
sudo systemctl restart xnch
systemctl is-active xnch          # expect: active
lsof ~/.xnch/graph.kuzu            # expect: ONLY the gateway PID now
curl -s http://127.0.0.1:8001/health   # expect: ok
/home/x-nch/xnchSystems/xnch/.venv/bin/python -m cli mcp test --skip-chat
```

Partial rollback (only if the memory-service misbehaves but its code is fine): keep remote env, just bounce the service:

```bash
sudo systemctl restart xnch-memory
curl -s -H "X-Internal-Token: $(grep '^XNCH_MEMORY_TOKEN=' ~/.xnch/xnch.env | tail -1 | cut -d= -f2-)" \
  http://127.0.0.1:8003/healthz
```

Re-apply remote mode after the rehearsal (restore final state):

```bash
sudo systemctl stop xnch
sed -i 's/^XNCH_MEMORY_EMBEDDED=true/XNCH_MEMORY_EMBEDDED=false/' ~/.xnch/xnch.env
sudo systemctl start xnch-memory && sudo systemctl start xnch
lsof ~/.xnch/graph.kuzu           # expect: only the xnch-memory PID again
curl -s http://127.0.0.1:8001/health
```

**Gate E:** rollback restores embedded mode with the gateway owning Kuzu and `mcp test --skip-chat` green; forward re-apply restores remote mode with the service owning Kuzu.

---

## Task F: Record the gate result + follow-ups

- [ ] **Step 1: Annotate the spec and runbook**

Append a review note to `docs/superpowers/specs/2026-09-11-micro-component-split.md` confirming T2.5/T2.6 done: service on `:8003`, gateway remote, Kuzu single-owner verified, rollback rehearsed. Update `docs/runbooks/memory-service-deploy.md` Step 1 order to "stop gateway first" (Kuzu safety) so service-first is never attempted against a live embedded gateway.
- [ ] **Step 2 (deferred, NOT part of this gate): Prometheus scrape**

`build_app` in `xnch/memory/server.py` does not wire `install_metrics_middleware` yet. Adding `/metrics` on `:8003` (same pattern as `xnch/main.py` `install_metrics_middleware`) + a scrape job for `192.168.50.1:8003` is a small code change + its own test cycle — out of scope for the cutover gate. Do it as a follow-up task.

---

## Ops Gates (recap)

| Gate | Condition to proceed |
|------|---------------------|
| 0 | Phase 2 published (xnch origin master + gitlink at `1a46511*`) |
| A | imports ok, port 8003 free, `XNCH_MEMORY_TOKEN` set, snapshot recorded |
| B | `xnch-memory` active, healthz `{postgres:true, kuzu:true}`, single Kuzu owner |
| C | gateway active, `/health` ok, Kuzu owned ONLY by `xnch-memory` |
| D | graph/recall via gateway, mcp tests green, SSE relay, consolidation 200, chat OK |
| E | embedded rollback rehearsed and forward state re-applied |