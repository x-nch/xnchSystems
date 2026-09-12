# Master Execution Plan: Micro-Component Split + Agentic Layer

**Date:** 2026-09-12
**Deliverable:** Run the micro-component split (Phase 1 consolidation, Phase 2 memory-service) to production, then build the Hermes + Gas Town + LangGraph agentic layer on top of the stabilized boundary.

> Required sub-skill: **superpowers:subagent-driven-development** (recommended) or **superpowers:executing-plans**. Load the sub-project plan file named in each Task before doing that task's work, then follow it exactly. This document sequences and gates them; it does not re-specify their steps.

## Goal

Five pre-authored documents describe a two-stage program. This plan sequences and gates that work and files the documents into their canonical homes:

| Root file (untracked) | Canonical home | Kind |
|-----------------------|----------------|------|
| `2026-09-11-micro-component-split.md` | `docs/superpowers/specs/2026-09-11-micro-component-split.md` | Spec |
| `2026-09-11-agentic-layer-hermes-gastown-langgraph.md` | `docs/superpowers/specs/2026-09-11-agentic-layer-hermes-gastown-langgraph.md` | Spec |
| `2026-09-11-phase1-capability-consolidation.md` | `docs/superpowers/plans/2026-09-11-phase1-capability-consolidation.md` | Plan |
| `2026-09-11-phase2-memory-service-extraction.md` | `docs/superpowers/plans/2026-09-11-phase2-memory-service-extraction.md` | Plan |
| `2026-09-11-agentic-layer-m1-m5.md` | `docs/superpowers/plans/2026-09-11-agentic-layer-m1-m5.md` | Plan |

The sub-plans already reference their specs at exactly these paths (`docs/superpowers/specs/2026-09-11-micro-component-split.md`, `docs/superpowers/specs/2026-09-11-agentic-layer-hermes-gastown-langgraph.md`), so filing the specs there is a hard prerequisite for the spec-status updates the sub-plans perform in their final tasks.

**Program success criteria (all must hold at the end):**

1. Micro-component split: `capability_agent` is the single governed-exec + read-only-fs capability sidecar on node-b `:8090`; old sidecar packages and legacy dispatch deleted; `xnch_mcp` targets the new sidecar via env flip with one-command rollback.
2. Micro-component split: L0–L3 memory extracted to `memory-service` on node-a `:8003` (entrypoint `python -m xnch.memory.server`), xnch gateway talking to it with `XNCH_MEMORY_EMBEDDED=1` rollback and degrade/replay path; Kuzu single-owner constraint resolved.
3. Agentic layer: proactivity surface excluded systems flagged off; MCP HTTP router is authenticated; `hermes` actor at `TRUSTED_AGENT` on node-b; Gas Town installed on the Mac with `agent-runner` retired; LangGraph supervisor graph enabled by default with HITL `interrupt()`; excluded subsystems deleted.
4. No https://xnch-systems.com contract regressions (frozen external contracts pass; additive-only tools).
5. All three sub-plans' spec-status updates committed — specs annotated complete (Phase 1 T1.1–T1.8, Phase 2 T2.1–T2.6) and agentic spec status rolled forward.
6. Submodule discipline held: changes inside `xnch/` and `nexi/` committed inside the submodule first, then the superrepo gitlink bumped in a separate commit.

## Architecture

Dependency chain (strict, checked before each stage):

```
micro-component-split spec ──┬──▶ Phase 1 plan (capability_agent) ──┬──▶ [gate] ─┐
                             └──▶ Phase 2 plan (memory-service)  ──┴──▶ [gate] ─┼─▶ agentic M1 ─▶ M2 ─▶ M3 ─▶ M4 ─▶ M5
agentic-layer spec ──────────────────────────────────────────────────────────────┘
```

- **Phase 1** and **Phase 2** are independently executable, but both must be **complete and verified in prod** before Agentic M1 starts (hard precedent in `agentic-layer-m1-m5.md` line 15). Recommended order: Phase 1 then Phase 2.
- Each agentic milestone (M1–M5) ends in deploy + verify; an ops gate sits at M1.2, M2.5, M3.3, and M4.4.
- The MCP stitching layer (`xnch_mcp`) is the single choke point that all three plans touch; it must stay green after every task that modifies it.

**Cross-plan invariants (enforced by this plan, owned in the sub-plans):**

| Invariant | Owned by |
|-----------|----------|
| External contracts frozen (`xnch_*`/`am_*` tool signatures, muse web UI, chat API, agent-runner dispatch); additive-only | all |
| Kuzu single-process / single-file ownership drives the Phase 2 extraction; never run two writers | Phase 2 T3 |
| Hermes gets no direct access to memory-service, capability sidecar, Postgres, or Kuzu — every governed action is a `xnch_*`/`am_*` MCP tool call through policy dry-run → trust tier → audit | Agentic spec |
| New actors max T1 autonomy; T2 reachable only via supervisor HITL `interrupt()` as SYSTEM | Agentic M4 |
| Env flips (`capability_*-first`, `XNCH_MEMORY_EMBEDDED`, `proactivity_surface_enabled`) are switch-only, no recompile | Ph1 T5/T6, Ph2 T2, M1.1 |
| Submodule commits land inside the submodule; gitlink bump is a follow-up superrepo commit | all |

## Tech Stack

FastAPI, uvicorn, httpx, pydantic-settings, pytest (asyncio_mode=auto), redis.asyncio, asyncpg, Kuzu, LangGraph, LangSmith, systemd (node-a/node-b), launchd (Mac), Hermes (Nous Research), Gas Town (gastownhall/gastown). Python 3.13 (repo floor).

## Spec

- `docs/superpowers/specs/2026-09-11-micro-component-split.md` (filed in Task 0) — phases/tasks T0.x, T1.x, T2.x; Approach A consolidate-then-extract
- `docs/superpowers/specs/2026-09-11-agentic-layer-hermes-gastown-langgraph.md` (filed in Task 0) — M1–M5 milestones, trust tiers, MCP choke point

## Global Constraints

- **Ops gates are user-run**: the plan marks `USER OPS GATE` steps; pause and hand the operator the exact commands + rollback before proceeding.
- **Single-home registry**: all capability tool home locations are updated in `AGENTS.md` (Phase 1 Task 8) before any removal task runs.
- **Verification first**: run the per-task tests and the frozen-contract golden tests after every task that touches `xnch_mcp`, `capability_agent`, memory stores, or dispatch.
- **Spec status kept current**: mark spec tasks complete with dates as sub-plans direct; never leave spec and implementation out of sync at a gate.
- **No new surface**: nothing outside the two specs gets built; anything discovered mid-execution goes back to the spec as a review note, not a silent addition.
- **Commit discipline**: one logical commit per sub-plan task; never bundle submodule bumps with code changes in the superrepo.

---

## Task 0: File the documents into canonical homes

- [ ] `mv 2026-09-11-micro-component-split.md docs/superpowers/specs/`
- [ ] `mv 2026-09-11-agentic-layer-hermes-gastown-langgraph.md docs/superpowers/specs/`
- [ ] `mv 2026-09-11-phase1-capability-consolidation.md docs/superpowers/plans/`
- [ ] `mv 2026-09-11-phase2-memory-service-extraction.md docs/superpowers/plans/`
- [ ] `mv 2026-09-11-agentic-layer-m1-m5.md docs/superpowers/plans/`
- [ ] Verify every `docs/superpowers/specs/...` reference inside the three plans resolves to the moved files: `rg -n "docs/superpowers/specs/" docs/superpowers/plans/ | rg -c "2026-09-11"` should match the expected spec mentions and none should dangle (paths are relative to repo root, so no content edits needed).
- [ ] `git add docs/superpowers/` and commit: `docs: file micro-split + agentic layer specs and plans`

**Verify:** `ls docs/superpowers/plans/2026-09-11-*` shows all three plans; `ls docs/superpowers/specs/2026-09-11-*` shows both specs; `git status --short` is clean apart from nothing new under repo root.

## Task 1: Phase 1 — build capability sidecar (headless)

Run per `2026-09-11-phase1-capability-consolidation.md`:

- [ ] Plan Task 1 (baseline verification) — confirm prod and submodules match assumptions before touching anything
- [ ] Plan Task 2 (xnch settings: `capability_token` + `capability_node_b_url`)
- [ ] Plan Task 3 (`capability_agent` exec router + app + entrypoint)
- [ ] Plan Task 4 (`capability_agent` fs router endpoints)
- [ ] Plan Task 5 (`xnch_mcp` retarget remote clients + capability-first settings fallback)
- [ ] Run the full Phase 1 test suite + the frozen-contract golden tests against `xnch_mcp`

**Verify (this task is the code gate for Task 2):** all Phase 1-prefixed and golden tests green in the superrepo CI-style local run before the operator cutover.

## Task 2: Phase 1 — infra prep + USER OPS GATE (node-b cutover)

Run per `2026-09-11-phase1-capability-consolidation.md`:

- [ ] Plan Task 6 Steps 1–5 (infra unit, policy allowlist, env docs, runbook) — done by the agent
- [ ] Plan Task 6 Step 6: **USER OPS GATE — run the cutover on node-b** — hand the operator the plan's exact commands and one-command rollback; do not proceed until they confirm the flip is live and the old sidecar is draining
- [ ] Record the gate result (date + operator confirmation) as a review note in the spec

**Verify:** sidecar answers on node-b `:8090` under the new unit; `xnch_mcp` dispatch shows capability-first; rollback path documented and rehearsed (dry-run echo of the env flip + restart).

## Task 3: Phase 1 — decommission, registry, boundary, final

Run per `2026-09-11-phase1-capability-consolidation.md`:

- [ ] Plan Task 7 (delete old sidecar packages — only after the gate passed)
- [ ] Plan Task 8 (AGENTS.md Single-Home Registry)
- [ ] Plan Task 9 (execution boundary audit → doc)
- [ ] Plan Task 10 (group clients under `clients/`)
- [ ] Plan Task 11 (final verification + submodule bump)
  - [ ] Commit inside `xnch/` submodule first, then bump the gitlink in the superrepo
  - [ ] Mark Phase 1 T1.1–T1.8 done in `docs/superpowers/specs/2026-09-11-micro-component-split.md` per plan
- [ ] Program-level spot check: old sidecar names absent from tree and `AGENTS.md`; no `xnch_mcp` reference to a deleted package

**Verify:** `pytest` green in superrepo; `git submodule status` shows the bumped `xnch` gitlink matching the submodule HEAD; spec annotated.

## Task 4: Phase 2 — server + client + bootstrap + swap (headless)

Run per `2026-09-11-phase2-memory-service-extraction.md`:

- [ ] Plan Task 1 (baseline + preconditions) and Task 2 (settings)
- [ ] Plan Task 3 (server: app factory, token, `/v1/call` whitelist dispatch)
- [ ] Plan Task 4 (`/healthz`, `/v1/consolidation/run`, `/v1/graph/stream` SSE, `__main__`)
- [ ] Plan Task 5 (client: `RemoteStoreRef` async + `RemoteGraphStore` sync)
- [ ] Plan Task 6 (degrade wrapper + replay loop)
- [ ] Plan Task 7 (bootstrap `build_memory()` embedded|remote)
- [ ] Plan Task 8 (gateway lifespan swap)
- [ ] Run the Phase 2 test suite + memory-routing tests + frozen-contract golden tests

**Verify (code gate for Task 5):** all Phase 2 and memory-routing and golden tests green; `XNCH_MEMORY_EMBEDDED=1` still exercises the in-process path.

## Task 5: Phase 2 — infra + USER OPS GATE (node-a cutover)

Run per `2026-09-11-phase2-memory-service-extraction.md`:

- [ ] Plan Task 9 Steps 1–6 (graph SSE relay from `xnch/routes/memory.py`, `xnch-memory.service`, runbook, env-vars doc, consolidation.service edit) — done by the agent
- [ ] Plan Task 9 Step 7: **USER OPS GATE — cutover on node-a** — hand the operator the plan's exact commands and one-command rollback (`XNCH_MEMORY_EMBEDDED=1`); do not proceed until confirmed
- [ ] Record the gate result as a review note in the spec

**Verify:** memory-service answers on node-a `:8003` (`/healthz`); gateway uses remote stores; Kuzu file open only by the service process; embedded rollback rehearsed.

## Task 6: Phase 2 — final verification + spec status + gitlink

Run per `2026-09-11-phase2-memory-service-extraction.md`:

- [ ] Plan Task 10 (final verification, submodule bump, spec status)
  - [ ] Commit inside `xnch/` submodule first, then bump the gitlink in the superrepo
  - [ ] Mark Phase 2 T2.1–T2.6 done in `docs/superpowers/specs/2026-09-11-micro-component-split.md`; move Open Question 3 (full code move, option a) to "deferred — boundary proving" per plan
- [ ] Confirm no `xnch_mcp` code path still `import`s a memory store directly (store access is behind gateway abstraction only)

**Verify:** superrepo green; `git submodule status` bumped; spec annotated; agentic prerequisite gate satisfied (Phase 1 + Phase 2 verified in prod — see `agentic-layer-m1-m5.md` line 15).

## Task 7: Agentic M1 + M2 — flag, security, Hermes

Run per `2026-09-11-agentic-layer-m1-m5.md`. M1 first, then M2:

- [ ] Task 1.1 (`proactivity_surface_enabled` flag)
- [ ] Task 1.2 (deploy env verification + regression; **USER OPS GATE** at Task 1.2 Step 1)
- [ ] Task 2.1 (MCP HTTP router authentication — resolves spec Open Question 1)
- [ ] Task 2.2 (`hermes` actor at `TRUSTED_AGENT`)
- [ ] Task 2.3 (skills sync `scripts/gen_agent_skills.py`)
- [ ] Task 2.4 (memory routing — add `hermes` to deprecation default)
- [ ] Task 2.5 (Hermes deployment + soak; **USER OPS GATE** at Task 2.5 Step 4)

**Verify:** M1 regression green; unauthenticated MCP requests rejected; `hermes` actor listed in registry with `TRUSTED_AGENT`; soak shows governed tool calls flowing through the MCP choke point with audit entries, zero direct-store access.

## Task 8: Agentic M3 — Gas Town + agent-runner retirement

Run per `2026-09-11-agentic-layer-m1-m5.md`:

- [ ] Task 3.1 (`GastownClient` + settings)
- [ ] Task 3.2 (`xnch_workstream_spawn` + `xnch_workstream_status` tools)
- [ ] Task 3.3 (Gas Town install + agent-runner retirement; **USER OPS GATE** — Mac launchd swap + removal confirmation)

**Verify:** burst workstream spawn/status round-trip works from the Mac; launchd template references Gas Town, agent-runner job removed; `agent-runner/` dispatch is unused (still in tree until M5).

## Task 9: Agentic M4 — LangGraph supervisor default

Run per `2026-09-11-agentic-layer-m1-m5.md`:

- [ ] Task 4.1 (relax the Phase 2 remote-memory guard)
- [ ] Task 4.2 (`workstream_supervisor` graph with HITL `interrupt()`)
- [ ] Task 4.3 (proactivity surface re-target)
- [ ] Task 4.4 (enable LangGraph by default; **USER OPS GATE** at Task 4.4 Step 1)

**Verify:** supervisor graph intercepts workstream launches; T2 token granted only via SYSTEM `interrupt()`; proactivity surface responds through the graph; regression suite green.

## Task 10: Agentic M5 — delete excluded code + program close

Run per `2026-09-11-agentic-layer-m1-m5.md`:

- [ ] Task 5.1 (delete excluded subsystems)
- [ ] Task 5.2 (flags + docs cleanup)
- [ ] Task 5.3 (final verification + spec status)
  - [ ] Mark agentic spec M1–M5 complete with dates; update status and any open questions per plan
- [ ] Program-level close: run full superrepo `pytest`; re-verify all six program success criteria above; `git submodule status` consistent; one final commit

**Verify:** excluded subsystems gone from `AGENTS.md` and tree; flags resolved; all six success criteria confirmed with the operator; spec and implementation in sync.

---

## Self-Review

- **Sequencing correct?** Yes — Phase 1 + Phase 2 gates precede M1; M1–M5 strictly sequential with per-milestone gates. Confirm both split ops gates passed in prod before Task 7 starts (agentic line 15).
- **Every task referenced?** Yes — every sub-plan task (P1: 1–11, P2: 1–10, M1.1–M5.3) appears exactly once across Tasks 1–10.
- **Spec/plan locations consistent?** Yes — Task 0 files specs to the exact paths the three plans reference; Task 0 is mandatory before any plan task that mutates spec status.
- **Rollback everywhere?** Yes — each ops gate carries a one-command rollback (env flip, `XNCH_MEMORY_EMBEDDED=1`, flag off).
- **Plausible timebox?** Tasks 1–3 ≈ 1–2 days; Tasks 4–6 ≈ 1–2 days; Tasks 7–10 ≈ 2–4 days, excluding operator gates and Hermes soak.
- **Not over-specified?** This plan deliberately does not repeat sub-plan step content — it sequences and gates. If a sub-plan needs correction, edit the sub-plan, not this file.

## Execution Handoff

Recommended: **superpowers:subagent-driven-development** — dispatch one subagent per sub-plan file (Phase 1 → Phase 2 → M1–M5), paused at each ops gate for the operator. Alternative: inline execution spearheaded by this plan with the sub-plan loaded per task.

Start with Task 0 (filing). The user's approval of this plan plus the operator's presence at the four gates (node-b cutover, node-a cutover, runtime env verification, LangGraph default) is the coordination contract.