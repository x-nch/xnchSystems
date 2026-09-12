# Agentic Layer — Hermes + Gas Town + LangGraph Execution Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute the agentic-layer milestones (M1 flag-off → M5 code deletion) from the spec, now that the micro-component split (Phase 1 + Phase 2) is verified complete. Adds Hermes (node-b, long-horizon autonomy), Gas Town (Mac, burst workstreams), and promotes LangGraph as the orchestration DSL — all governed through the single MCP bridge choke point.

**Architecture:** Three tempos federated by governance: interactive (nexi + LangGraph decision graphs via the gateway), long-horizon (Hermes as `TRUSTED_AGENT` actor), burst (Gas Town workstreams spawned via `xnch_workstream_spawn`). Every agent action is an `xnch_*`/`am_*` MCP tool call that flows policy dry-run → trust tier → audit. New actors get at most T1; the T2 spawn boundary is crossed only via the supervisor graph's HITL `interrupt()` running as SYSTEM.

**Tech Stack:** FastAPI, httpx, LangGraph (`langgraph`, `langgraph.types.Command`, `MemorySaver`), pytest (asyncio_mode=auto), systemd (nodes A/B), launchd (Mac), Hermes Agent (Nous Research), Gas Town (gastownhall/gastown), Pydantic-settings.

**Specs referenced:**
- `docs/superpowers/specs/2026-09-11-agentic-layer-hermes-gastown-langgraph.md` (authoritative)
- `docs/superpowers/plans/2026-09-11-agentic-layer-m1-m5.md` (detailed per-task steps + test snippets)
- `docs/superpowers/specs/2026-09-11-micro-component-split.md` (Phase 1 / Phase 2 prerequisite gates)

## Global Constraints

- **Prerequisite verified:** Phase 1 (capability sidecar merge) and Phase 2 (memory-service extraction) both COMPLETE (2026-09-12); see "Current state validation" below. M1 may not start until the agent-runner dispatch queue is confirmed idle (operator gate).
- External contracts frozen: pre-existing `xnch_*`/`am_*` tool signatures, muse UI, chat API. New tools are **additive only** (`xnch_workstream_spawn`, `xnch_workstream_status`).
- `xnch/` and `nexi/` are git submodules — submodule commit first, then superrepo gitlink bump. `xnch_mcp/`, `scripts/`, `infra/`, `capability_agent/`, `clients/` are superrepo packages.
- Fail-closed auth everywhere new: `XNCH_MCP_HTTP_TOKEN`, `XNCH_MEMORY_TOKEN` (already deployed from Phase 2), `XNCH_GASTOWN_TOKEN`. No anonymous tool path after M2.2.
- `pytest` from repo root with repo `.venv` active. `asyncio_mode = auto`.
- Ops steps (install, systemd/launchd, env changes on real hosts) are **USER OPS**, executed by the operator; the coding agent commits config + unit files only and leaves a runbook.
- Kuzu ownership rule: exactly one process owns the graph DB file. Embedded mode → gateway owns it; service mode → `xnch-memory.service` owns it. Never both (the Phase 2 cutover already established this).

## Current state validation

Read from `docs/superpowers/specs/2026-09-11-micro-component-split.md`:

- **Phase 1 — COMPLETE (2026-09-12).** Gate A + Gate B passed; `capability_agent/` sidecar active on node-b :8090; `exec_agent/` and `fs_read_agent/` packages and their systemd units deleted; `xnch_mcp` remote clients retargeted to `/exec/*` + `/fs/*` with legacy-fallback settings; `AGENTS.md` Single-Home Registry updated; clients grouped under `clients/`.
- **Phase 2 — COMPLETE (2026-09-12).** Gate 0–E passed; `xnch-memory.service` active on node-a :8003 (`{"status":"ok","tiers":{"postgres":true,"kuzu":true}}`); gateway remote (`XNCH_MEMORY_EMBEDDED=false`, `XNCH_MEMORY_SERVICE_URL=…`, fail-closed token); Kuzu single-owner verified both directions; `/memory/graph/stream` relay + SSE verified; `consolidation.service` re-targeted with token; rollback rehearsed (`XNCH_MEMORY_EMBEDDED=true` one-command revert).
- **Prerequisite gate satisfied** for M1: `xnch/` now runs with remote memory (Phase 2 guard in `xnch/main.py` is `langgraph_pipeline and memory_embedded`).
- **Spec prerequisite:** micro-component split Phase 1 + Phase 2 complete and verified in prod — **MET**. The Phase-2 `RemoteStoreRef`/`RemoteGraphStore` refs that M4 needs were built in Task 5; M4.2 just removes the `memory_embedded` guard around the LangGraph pipeline.

**Open Questions still open (resolved per-milestone in the plan):** OQ1 Hermes→gateway auth (= M2.2: static `XNCH_MCP_HTTP_TOKEN`), OQ2 Gas Town reachability (= M3.1: direct POST gateway→Mac over tailscale, poll fallback), OQ3 external channel (deferred), OQ4 trajectory export cadence (decide after M2 soak).

### File Structure (new/modified only; Phase 1/2 files already moved)

```
xnch/security/trust_model.py                 # MODIFY — add hermes actor (M2.2 submodule)
xnch/config.py                               # MODIFY — mcp_http_token (M2.2), memory flags already set (M4.2 relax)
xnch_mcp/http_router.py                      # MODIFY — X-MCP-Token auth gate (M2.2)
xnch_mcp/handlers/workstream.py              # NEW — spawn (T2) + status (T0) (M3.2)
xnch_mcp/handlers/memory.py                  # MODIFY — proactivity surface re-target (M4.4)
xnch_mcp/registry.py                         # MODIFY — import + register workstream module (M3.2)
scripts/gen_agent_skills.py                  # NEW — SKILL.md generator (M2.3)
xnch/agents/supervisor_graph.py              # NEW — workstream spawn supervisor (M4.3)
infra/no-k3s/node-b/systemd/hermes.service   # NEW (M2.5)
clients/gastown/com.xnch.gastown.plist       # NEW (M3.1)
docs/runbooks/hermes-deploy.md               # NEW (M2.5)
docs/runbooks/gastown-deploy.md              # NEW (M3.1)
```

---

## MILESTONE 1 — Flag off the excluded subsystems

Prerequisite: Phase 1+2 prod verified (gate below). This milestone only gates deployment; most code is already deleted in Phase 1 (`nexi/goal`, `nexi/proactivity`, `nexi/workflow`, `xnch/jobs/goal_dispatch`, `workflow_schedule`, `workflow_store`, `agent_run_store`, `clients/agent-runner`) — the agentic-layer spec lists them under M5 deletion, but Phase 1 already removed the capability sidecars they depended on. Verify they're still referenced nowhere.

### Task 1.1: `_memory_surface` proactivity flag + deploy-env verification

**Files:** `xnch/config.py`, `xnch_mcp/handlers/memory.py:46-52`; test `xnch_mcp/tests/test_memory_surface_flag.py` (provided in M1 plan).

- [ ] **Step 1: Write failing test** — provided in `docs/superpowers/plans/2026-09-11-agentic-layer-m1-m5.md:48-94`.
- [ ] **Step 2: Run to verify failure** — `pytest xnch_mcp/tests/test_memory_surface_flag.py -v` → fails, no `_proactivity_enabled`.
- [ ] **Step 3: Implement** — add `proactivity_surface_enabled: bool = True` to `xnch/config.py`; guard `_memory_surface` with `_proactivity_enabled()` returning the setting.
- [ ] **Step 4: Tests pass** — `pytest xnch_mcp/tests/test_memory_surface_flag.py -v` → 2 PASS.
- [ ] **Step 5: Commit (submodule)** — `git -C xnch add xnch/config.py xnch_mcp/handlers/memory.py xnch_mcp/tests/test_memory_surface_flag.py` → `feat: proactivity_surface_enabled flag`; then superrepo gitlink bump.

### Task 1.2: USER OPS gate — confirm excluded subsystems are inert

- [ ] **Step 1: Operator** — verify deployed envs `~/.xnch/xnch.env` (node-a) and `~/.xnch/nexi.env` (node-b) contain none of `XNCH_GOAL_DISPATCH_ENABLED=true`, `NEXI_GOAL_DRIVER_ENABLED=true`, `NEXI_WORKFLOW_EXECUTOR_ENABLED=true`, `XNCH_WORKFLOW_EXECUTOR_ENABLED=true`, `XNCH_LANGGRAPH_PIPELINE=true`. Restart gateway + nexi; confirm scheduler log shows only `session_ingest`, consolidation, memory-service health.
- [ ] **Step 2: Regression** — `pytest --tb=short -q` green; `python -m clients.cli mcp test --skip-chat` green; muse UI loads.

---

## MILESTONE 2 — Hermes on node-b

### Task 2.1: MCP HTTP router token auth (resolves spec OQ1)

**Files:** `xnch/config.py` (`mcp_http_token: str = ""`), `xnch_mcp/http_router.py`; test `xnch_mcp/tests/test_http_router_auth.py` (provided M2 plan:48-218).

- [ ] Write failing tests (4 cases: missing token 401, wrong token 401, valid token 200, unset=back-compat 200).
- [ ] Implement `_verify_mcp_token` using `secrets.compare_digest`; attach as `Depends` on `/tools`, `/tools/openai`, `/servers`, `/call`, `/call/batch`.
- [ ] `pytest xnch_mcp/tests/test_http_router_auth.py` → 4 PASS; existing `xnch_mcp/tests/` green.
- [ ] Commit: `git -C xnch add xnch/config.py` → `feat: mcp_http_token setting`; `git add xnch_mcp/http_router.py xnch_mcp/tests/test_http_router_auth.py` → `feat(mcp): token auth for HTTP router (prereq for external agents)`; bump gitlink.

### Task 2.2: `hermes` actor at TRUSTED_AGENT

**Files:** `xnch/security/trust_model.py` (`ACTOR_TRUST_MAP`); test `xnch/tests/test_hermes_actor.py` (provided M2 plan:263-279).
- [ ] Failing tests: `test_hermes_trust_level`, `test_hermes_max_tier`.
- [ ] Add `"hermes": TrustLevel.TRUSTED_AGENT` to `ACTOR_TRUST_MAP`.
- [ ] `pytest xnch/tests/test_hermes_actor.py -v` → 2 PASS.
- [ ] Commit (submodule).

### Task 2.3: Skills sync — `scripts/gen_agent_skills.py`

**Files:** `scripts/gen_agent_skills.py` (new), `scripts/__init__.py` (new — makes `from scripts.gen_agent_skills import generate_skills` work), test `tests/test_gen_agent_skills.py` (provided M2 plan:302-340).
- [ ] Failing tests: `test_generates_skill_md`, `test_no_tools_no_files`.
- [ ] Implement (provided M2 plan:348-408) — one `SKILL.md` per `ToolDef`.
- [ ] `pytest tests/test_gen_agent_skills.py -v` → 2 PASS.
- [ ] Commit (superrepo).

### Task 2.4: Memory routing — add `hermes` to deprecation default

**Files:** `xnch/memory/routing_policy.py` (~line 33 + ~line 41); test extension `xnch/tests/test_memory_routing_policy.py` (provided M2 plan:423-430); infra `infra/no-k3s/shared/memory-routing.example.yaml`.
- [ ] Failing test asserts default `deprecate_store_note_for` contains `nexi` and `hermes`.
- [ ] Change both default constructions to `frozenset({"nexi", "hermes"})`; example YAML updated.
- [ ] Commit (submodule + superrepo example).

### Task 2.5: Hermes deploy unit + runbook + soak (USER OPS)

- [ ] Create `infra/no-k3s/node-b/systemd/hermes.service` (lifecycle-only, env file `/home/x-nch/.xnch/hermes.env`).
- [ ] Create `docs/runbooks/hermes-deploy.md` (install, skills sync `python scripts/gen_agent_skills.py --out <hermes-skills-dir>`, soak checklist).
- [ ] **USER OPS** — operator installs Hermes per upstream docs, starts `hermes.service`, sets `XNCH_MCP_TOKEN`+`X-Actor-Role=hermes` in `hermes.env`, runs soak checklist. Block M3 until checklist item 5 (full automation chain in DecisionLedger) passes.
- [ ] Commit unit + runbook; bump gitlinks.

---

## MILESTONE 3 — Gas Town on the Mac

### Task 3.1: `GastownClient` + settings

**Files:** `xnch/config.py` (`gastown_url`, `gastown_token`); new `xnch_mcp/gastown.py`; test `xnch_mcp/tests/test_gastown_client.py` (provided M2 plan:524-572).
- [ ] Failing tests (2 unit + 1 error path) — spawn POSTs to `/api/workstreams`, status hits GET, 5xx raises `GastownError`.
- [ ] Implement `GastownClient(base_url, token, timeout, transport)` with `spawn()` + `status()`; `raise_for_status` mapped to `GastownError`.
- [ ] **USER OPS** at M3.3 confirms real Gas Town paths; if they differ, fix path constant + add regression test.
- [ ] Commit (submodule config; superrepo client).

### Task 3.2: `xnch_workstream_spawn` (T2) + `xnch_workstream_status` (T0)

**Files:** `xnch_mcp/handlers/workstream.py` (new, provided M2 plan:673-764), `xnch_mcp/registry.py` (`_load_handlers` import + module tuple), test `xnch_mcp/tests/test_workstream_handlers.py` (provided M2 plan:597-669).
- [ ] Failing tests: tier assertions, spawn calls gastown + emits audit, status stores terminal outcome as `workstream` episode (idempotent via `has_identical_recent`).
- [ ] Implement handlers following the scraper-handler pattern; register in `_load_handlers`.
- [ ] `pytest xnch_mcp/tests/test_workstream_handlers.py -v` → 3 PASS; `pytest xnch_mcp/tests/test_registry.py -q` shows +2 tools, additive-only diff (golden test).
- [ ] Commit (superrepo).

### Task 3.3: Gas Town install + agent-runner retirement (USER OPS)

- [ ] **USER OPS** — operator installs Gas Town per docs, loads `com.xnch.gastown.plist`, init workspace root `~/xnch-workstreams/`, confirms HTTP API responds.
- [ ] Create `clients/gastown/com.xnch.gastown.plist` (template mirroring retired `com.xnch.agent-runner.plist`).
- [ ] Create `docs/runbooks/gastown-deploy.md` (cutover, tailscale reachability from node-a, end-to-end spawn→status→`xnch_memory_recall` of outcome).
- [ ] **USER OPS** — `launchctl unload ~/Library/LaunchAgents/com.xnch.agent-runner.plist`; leave `clients/agent-runner/` code until M5.
- [ ] Commit plist + runbook.

---

## MILESTONE 4 — LangGraph consolidation

### Task 4.1: Relax the Phase 2 remote-memory guard

**Files:** `xnch/main.py` (LangGraph guard, ~lines 234-250); test `xnch/tests/test_langgraph_remote_mode.py` (provided M2 plan:822-842).
- [ ] Failing test: source no longer contains `"requires XNCH_MEMORY_EMBEDDED=1"`.
- [ ] Delete the `elif settings.langgraph_pipeline:` warning branch; change guard to `if settings.langgraph_pipeline:`; `PipelineRuntime` now receives the Phase-2 `s.memory.*` refs (the `RemoteGraphStore` is sync, so the ~15 sync call sites are unchanged).
- [ ] `pytest xnch/tests/test_langgraph_remote_mode.py` PASS; existing HITL tests green with `XNCH_MEMORY_EMBEDDED=false`.
- [ ] Commit (submodule).

### Task 4.2: Promote the 12-step pipeline as LangGraph decision graph

**Files:** `xnch/agents/pipeline_graph.py` + `xnch/agents/pipeline_runtime.py` (promote from opt-in to default-on; `PipelineRuntime` already has checkpointer + interrupt extraction + `parse_resume_decision`).
- [ ] Convert the nexi 12-step pipeline expression into LangGraph `StateGraph` nodes (one per step) with native `interrupt()` for T2 HITL; approval resume calls `parse_resume_decision`.
- [ ] Tests: graph compiles, HITL interrupt/resume round-trip, remote-memory refs resolve.
- [ ] `pytest xnch/tests/test_pipeline_graph.py xnch/tests/test_pipeline_hitl.py -q` green.
- [ ] Commit (submodule).

### Task 4.3: `workstream_supervisor` graph

**Files:** `xnch/agents/supervisor_graph.py` (new); test `xnch/tests/test_supervisor_graph.py` (provided M2 plan:865-927).
- [ ] Failing tests: non-coding goal → `none`; coding intent → `interrupt()` → approve `Command(resume=True)` → spawn; reject `Command(resume=False)` → `rejected`.
- [ ] Implement `build_supervisor(checkpointer=None) -> CompiledGraph` (decide heuristic + gate interrupt + SYSTEM-actor spawn via the M3.2 tool).
- [ ] `pytest xnch/tests/test_supervisor_graph.py -v` → 3 PASS.
- [ ] Commit (submodule).

### Task 4.4: Proactivity surface re-target

**Files:** `xnch_mcp/handlers/memory.py` (`_memory_surface`); test extension (provided M2 plan:946-956).
- [ ] Failing test asserts `_memory_surface` reads `pg_episodic.fetch_by_type("workstream"/"automation")`.
- [ ] Replace `ProactivityEngine` path with `pg_episodic.fetch_by_type` loop (graceful when `pg_episodic` absent).
- [ ] Update M1 engine test to new contract; `pytest xnch_mcp/tests/test_memory_surface_flag.py -v` green.
- [ ] Commit (superrepo).

### Task 4.5: Enable LangGraph by default (USER OPS)

- [ ] **USER OPS** — set `XNCH_LANGGRAPH_PIPELINE=true` in node-a env; restart gateway; e2e chat pass + one HITL approval round-trip in muse.
- [ ] Commit gitlink bump for the xnch submodule (Tasks 4.1–4.3).

---

## MILESTONE 5 — Delete the excluded code + docs

### Task 5.1: Inventory + delete excluded subsystems

- [ ] `rg -n "workflow_store|agent_run_store|goal_dispatch|workflow_schedule|nexi\.goal|nexi\.workflow|nexi\.proactivity|ProactivityEngine" xnch nexi xnch_mcp tests --type py | grep -v "agents/"` — fix surprises first.
- [ ] Delete (submodule by submodule): `nexi/nexi/goal/`, `nexi/nexi/proactivity/`, `nexi/nexi/workflow/`, `xnch/xnch/jobs/goal_dispatch.py`, `xnch/xnch/jobs/workflow_schedule.py`, `xnch/xnch/memory/workflow_store.py`, `xnch/xnch/memory/agent_run_store.py`; then superrepo `git rm -r clients/agent-runner` (Phase 1 already deleted sidecar dirs).
- [ ] Fix dangling route imports in `xnch/main.py`, `xnch/routes/__init__.py` — **keep** approvals/HITL routes (served the new interrupts).
- [ ] `pytest --tb=short -q` green.
- [ ] Commits: submodule `chore: remove excluded goal/proactivity/workflow subsystems`; gitlink bumps; superrepo `chore: remove agent-runner`.

### Task 5.2: Flags + docs cleanup

- [ ] Remove dead flags (`goal_dispatch_*`, `workflow_executor_enabled` both nodes, nexi `goal_driver_*`/`workflow_poll_*`/`goal_default_*`) only after confirming zero references.
- [ ] Keep `proactivity_surface_enabled` + `langgraph_pipeline`. Update `AGENTS.md` Single-Home Registry: scheduling→Hermes (node-b), workstreams→Gas Town (Mac) via `xnch_workstream_*`, graphs→`xnch/agents/`.
- [ ] Commit docs.

### Task 5.3: Final verification

- [ ] E2E: soak automation chain in DecisionLedger; `xnch_workstream_spawn`→`status`→`xnch_memory_recall` round-trip; HITL interrupt/resume in muse; `pytest` full green; `python -m clients.cli mcp test --skip-chat`.
- [ ] Contract: MCP registry contains all pre-existing tools byte-identical + exactly 2 new (`xnch_workstream_*`).
- [ ] Update spec statuses (mark M1–M5 implemented; resolve OQ1–OQ2 with chosen answers). Commit.

---

## Test strategy (consolidated from spec §8 + both plans)

| Layer | What |
|---|---|
| Unit | workstream handler (mock Gas Town HTTP), skills-sync generator output, trust-model `hermes` role, `GastownClient` paths |
| Contract | golden-file MCP tool-def test: pre-existing signatures byte-identical; only additive entries (+2) |
| Integration | LangGraph decision graph over Phase-2 remote-memory refs; HITL interrupt/resume round-trip; `/v1/call` whitelist dispatch |
| E2E (staged) | M2 soak automation; M3 spawn→status→episode round-trip via `python -m clients.cli mcp test`; M5 full e2e |
| Audit | every M2/M3/M4/M5 flow produces DecisionLedger entries — verified by test + `journalctl -u xnch`/`hermes`/`xnch-memory` |

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-09-12-agentic-layer-hermes-gastown-langgraph.md`.

**Recommended approach: Subagent-Driven** — dispatch a fresh `general` subagent per task above, review between tasks. Phase 1/2 prerequisites are already satisfied; the only **USER OPS** gates are M2.5 (Hermes soak), M3.1/M3.3 (Gas Town install + agent-runner retirement), M4.5 (langgraph default flip), and M4.1's existing tests. Subagents own the code/test commits; the operator executes only the ops steps.

**Dependency order (critical path):**
```
1.2 → 1.1 (ops gate) → 2.1 → 2.2 → 2.3 → 2.4 → 2.5(ops)
                                     → 3.1 → 3.2 → 3.3(ops)
                                     → 4.1 → 4.2 → 4.3 → 4.4 → 4.5(ops)
                                     → 5.1 → 5.2 → 5.3
```
M2 and M3 are independent after M1; M4 depends on M2 (auth) for the supervisor graph's SYSTEM spawn path being safe. M5 must be last (deletes code M2–M4 rely on).
