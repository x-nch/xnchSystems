# Agentic Layer — Hermes + Gas Town + LangGraph Integration Design

**Date:** 2026-09-11
**Status:** Approved direction — **sequenced AFTER the micro-component split**
**Depends on:** `2026-09-11-micro-component-split.md` Phase 1 + Phase 2 both complete and verified in prod (Phase 1 Task 6 ops gate, Phase 2 Task 9 ops gate). Do not start M1 before those are confirmed.
**Approach:** Federated by tempo — nexi+LangGraph (interactive), Hermes (long-horizon autonomy), Gas Town (burst workstreams), all governed through one MCP choke point.

---

## 1. Executive Summary

The current agent/workflow/goal machinery (`nexi/goal|proactivity|workflow`, `xnch/jobs/goal_dispatch|workflow_schedule`, `workflow_store`, `agent_run_store`, Mac agent-runner) is retired and replaced by an agentic layer built from three preferred components:

- **Hermes Agent** (Nous Research) on node-b — always-on autonomous agent: scheduled automations, sub-agents, skills. Runs as a `TRUSTED_AGENT` actor whose every governed action flows through the gateway MCP bridge.
- **Gas Town** (gastownhall/gastown) on the Mac — multi-agent workspace manager coordinating coding agents (opencode, Claude Code, etc.) in git-backed workspaces. Replaces the Mac agent-runner.
- **LangGraph** — promoted from opt-in to the platform's first-class graph layer: decision graphs (12-step pipeline with native HITL `interrupt()`) and supervisor graphs (when to spawn workstreams/automations).

**Core invariant — one choke point:** every governed action by any agent flows through the MCP bridge as `xnch_*`/`am_*` tool calls → policy dry-run → trust tier → audit chain. Agents are new *callers*, never new *paths*. Hermes gets no direct access to memory-service, capability sidecar, Postgres, or Kuzu.

**Human surface:** platform-only (muse web UI via tailscale funnel; remote HITL approvals included). No external messaging channels initially; adding one Telegram channel later is an additive, reversible config change.

**Cost:** 2 new services → 9 app-level deployables (envelope was 6–8; acknowledged).

### What is excluded vs kept (precision)

| Excluded (flag-off in M1, deleted in M5) | Kept and re-targeted (governance spine) |
|---|---|
| `nexi/goal/` (driver, planner) | `xnch/policy/` engine, `xnch/security/` guards |
| `nexi/proactivity/` | HITL approvals core (`xnch/agents/hitl.py` + approvals router) — fed by agent tool calls |
| `nexi/workflow/` | `xnch/agents/pipeline_graph.py` + `pipeline_runtime.py` (LangGraph runtime — promoted, rebuilt) |
| `xnch/jobs/goal_dispatch.py`, `workflow_schedule.py` | `xnch/agents/decision_state.py` (decision state) |
| `xnch/memory/workflow_store.py`, `agent_run_store.py` | `xnch/jobs/session_ingest.py`, `consolidation.py` (memory pipeline — untouched) |
| `clients/agent-runner` (Mac launchd worker) | Mac itself becomes the Gas Town host |
| Old proactivity surface (`ProactivityEngine` pending events) | |

---

## 2. Platform Baseline (assumed complete from the split)

| Service | Node | Port | Role |
|---|---|---|---|
| xnch gateway | a | :8001 | policy, trust tiers, HITL, audit, MCP bridge (HTTP router) |
| memory-service | a | :8003 | L0–L3 stores, `/v1/call` whitelist, consolidation |
| nexi | b | :8000 | 12-step decision pipeline, persona, chat |
| capability sidecar | b | :8090 | governed exec + read-only fs |
| agentmemory | — | :3111 | curated knowledge (`am_*`) |
| web (muse) | a | — | UI, HITL approvals (tailscale-funnel remote access) |
| perception | a | :8002 | voice/vision (untouched) |
| vLLM / LiteLLM | b | :8082 / :4000 | local Ornith inference / OpenAI-compatible proxy |
| **hermes ★NEW** | **b** | (hermes) | long-horizon autonomy |
| **gastown ★NEW** | **Mac** | (gastown) | burst coding workstreams |

---

## 3. Goals, Non-Goals, Success Criteria

### Goals
1. Autonomous scheduling/proactivity **without bespoke platform code** — Hermes owns it.
2. Parallel multi-agent coding workstreams with **git-backed state** — Gas Town owns it.
3. LangGraph as the **single orchestration DSL** for decisions, HITL, and spawn-supervision.
4. **Zero governance holes**: every agent action policy-checked, trust-tiered, audited, HITL-gated where T2.
5. Training data flywheel: trajectories from governed agent actions → Hermes MLOps ShareGPT export → xnch-train QLoRA.

### Non-Goals
- No external messaging channels (Telegram/Discord/...) in this phase.
- No changes to the memory-service, capability sidecar, or split-spec contracts.
- No multi-tenant actors — single-owner homelab.
- No rewrite of the nexi 12-step pipeline semantics (only its expression as LangGraph graphs).

### Success Criteria
- A Hermes automation runs unattended, exercises recall (`xnch_memory_*`), executes a governed command (sidecar via `xnch_exec_run`), requests and receives a HITL approval through muse, and every step appears in the DecisionLedger.
- A workstream spawned via `xnch_workstream_spawn` produces a completed git-backed result on the Mac, queryable via `xnch_workstream_status`, outcome stored as an episode.
- All pre-existing MCP tool signatures unchanged (new tools are additive only).
- The excluded subsystems' code is deleted with `pytest` green and muse UI/chat unaffected.

### Constraints
- External contracts frozen: existing `xnch_*`/`am_*` tool signatures, muse UI, chat API.
- Hermes's own persistent memory is **scratch only**; durable facts via `am_*` (policy-enforced, Phase 1 memory-routing pattern).
- Gas Town workspaces live in git checkouts; the gateway never writes to them directly.
- 2 nodes + Mac; systemd (nodes) + launchd (Mac).

---

## 4. Target Architecture

```
                     ┌──────────── node-a (i7) ────────────┐
 you ──muse UI────►  │ gateway :8001                        │
 (tailscale funnel   │  ├─ policy engine + trust tiers      │
  for remote HITL)   │  ├─ HITL approvals (re-targeted)     │
                     │  ├─ MCP bridge (HTTP router) ◄─┐     │
                     │  └─ LangGraph runtime + graphs │     │
                     │ memory-service :8003           │     │
                     └────────────────────────────────┼─────┘
                     ┌──────────── node-b (i9) ───────┼─────┐
                     │ nexi :8000 (interactive tempo)  │     │
                     │ HERMES ★ — always-on autonomy ──┘     │
                     │   ├─ scheduled automations, sub-agents│
                     │   ├─ TRUSTED_AGENT actor              │
                     │   ├─ model: LiteLLM :4000 (local)     │
                     │   └─ skills: SKILL.md from registry   │
                     │ capability sidecar :8090              │
                     │ vLLM :8082 / LiteLLM :4000            │
                     └───────────────────────────────────────┘
                     ┌──────────── Mac ──────────────────────┐
                     │ GAS TOWN ★ — burst workstreams        │
                     │  ├─ coding agents (opencode, etc.)    │
                     │  ├─ git-backed workspaces (queue=git) │
                     │  └─ launchd (replaces agent-runner)    │
                     └───────────────────────────────────────┘
```

### The three tempos

| Tempo | Owner | Trigger | Governance |
|---|---|---|---|
| Interactive | nexi + LangGraph | chat turn (muse/cli) | unchanged 12-step policy dry-run + HITL |
| Long-horizon | Hermes | schedule / self-directed / supervisor graph | MCP bridge → policy → audit; T2 needs HITL |
| Burst workstream | Gas Town | `xnch_workstream_spawn` (human or Hermes) | spawn is T2_EXEC + HITL; git state auditable; results → memory |

---

## 5. Component Specs

### 5.1 Hermes (node-b)

- **Identity**: actor role `hermes` at TRUSTED_AGENT tier (extend the trust-model role map; `xnch/security/trust_model.py`).
- **Tool path**: Hermes MCP client → gateway HTTP MCP router (`xnch_mcp/http_router.py`, mounted at gateway) → tools. Authentication: gateway secret/token flow resolved at implementation (Open Question 1) — must present an actor context, never an anonymous bypass.
- **Model**: primary LiteLLM `:4000` (local Ornith, OpenAI-compatible); fallback OpenRouter (existing model-selector pattern).
- **Scheduling**: Hermes native automations own everything `goal_dispatch`/`proactivity` used to do. The proactivity surface in `xnch_mcp/handlers/memory.py::_memory_surface` re-targets (flag-gated, M4) to read automation outcomes (episodes of type `automation`) instead of `ProactivityEngine` pending events.
- **Memory**: internal scratch permitted and ephemeral; durable facts via `am_memory_save`/`am_memory_lesson_save`. Extend the memory-routing deprecation list with `hermes` alongside `nexi`.
- **Skills sync**: a generator (`scripts/gen_agent_skills.py`, M2) emits one SKILL.md (agentskills.io format, Hermes-native) per `xnch_mcp` registry tool into Hermes's skills dir — platform capabilities become discoverable, versioned artifacts.
- **Unit**: `infra/no-k3s/node-b/systemd/hermes.service` (install per Hermes docs; unit manages lifecycle only).
- **MLOps**: enable Hermes trajectory export → `xnch-train/` ingest (ShareGPT). Cadence deferred (Open Question 4).

### 5.2 Gas Town (Mac)

- **Install**: per gastownhall/gastown docs; launchd template `com.xnch.gastown.plist` (mirrors the retired agent-runner plist pattern).
- **Gateway surface — two NEW MCP tools** (additive; existing signatures untouched):
  - `xnch_workstream_spawn` (T2_EXEC): payload `{title, goal, workspace_hint?, agent_hint?}` → POST to Gas Town's HTTP API on the Mac (gateway → Mac over tailscale/LAN). Requires HITL approval when unattended.
  - `xnch_workstream_status` (T0_READ): `{workstream_id?}` → active/completed/failed workstreams from Gas Town.
- **Queue semantics**: the excluded `agent_run_store` dispatch queue is NOT replaced by another queue — Gas Town's git-backed state is the queue.
- **Results**: on completion, a workstream outcome is stored via `xnch_memory_*` as an episode (type `workstream`) + audit event. Polling (gateway-side, on `xnch_workstream_status` calls and a low-frequency cron) — no Mac→gateway inbound requirement beyond what exists (Open Question 2 recommends direct POST; poll fallback documented).
- **Sleep tolerance**: workstreams pause on Mac sleep, resume from git hooks on wake — acceptable for burst tempo; Hermes-style scheduled work never runs on the Mac.

### 5.3 LangGraph (gateway, promoted)

- **Role A — decision graphs**: the nexi 12-step pipeline expressed as LangGraph state graphs; HITL for T2 actions via native `interrupt()`; approval resolution resumes the graph.
- **Role B — supervisor graphs**: small graphs deciding when to spawn Hermes automations or Gas Town workstreams (callable from chat or Hermes tool calls). Minimal scope: one `workstream_supervisor` graph.
- **Phase 2 guard relaxed**: `pipeline_runtime` operates in remote-memory mode via the Phase 2 client refs (`RemoteGraphStore` sync proxy + async refs were built for exactly this). Remove the `memory_embedded`-only guard once covered by tests.
- **Location**: runs in the gateway process (node-a) as today (`settings.langgraph_pipeline`), now default-on after M4.

### 5.4 Governance spine (re-targeted, unchanged in kind)

- HITL approvals become first-class gateway entities: raised by the MCP tool layer when policy demands, surfaced in muse, resolved via web/cli. Resolution resumes the caller — LangGraph interrupt for graphs, tool-result for Hermes, spawn-result for Gas Town.
- Policy engine, trust tiers, actor sandbox, injection/memory guards, EventLog + DecisionLedger: untouched.
- New actor: `hermes` (TRUSTED_AGENT). Gas Town coding agents act inside their workspaces only; their platform interactions (if any) go through the same bridge under the spawning actor's identity.

---

## 6. Data Flow

```
INTERACTIVE  you → muse/cli → gateway → nexi (LangGraph 12-step) → MCP tools → sidecar/memory
AUTONOMOUS   Hermes trigger → gateway MCP → policy dry-run → execute (sidecar / memory / am_*)
                                └─ T2? → HITL approval → muse (tailscale remote ok) → resume
WORKSTREAM   you/Hermes → xnch_workstream_spawn (T2 + HITL) → Gas Town (Mac)
             → coding agents in git workspaces → completion → outcome episode + audit
                                → xnch_workstream_status (T0) reads anytime
TRAINING     governed trajectories → Hermes MLOps export (ShareGPT) → xnch-train QLoRA
```

## 7. Error Handling

| Failure | Behavior |
|---|---|
| Hermes automation fails | Hermes-native retry/backoff; failure episode + muse surface; never silent (always-on host) |
| Gas Town workstream fails | git state preserved; status tool reports `failed`; human reviews workspace |
| Policy denies agent action | tool returns denial (as today); agent adapts or requests HITL; denial audited |
| Gateway unreachable (Mac) | workstreams continue locally; status syncs on reconnect |
| Gateway unreachable (Hermes) | tools fail closed; automations retry next cycle |
| Memory outage | Phase 2 degrade path (recall → `[]`, writes → replay queue) covers all callers |
| Mac asleep at spawn time | spawn returns `deferred`; Gas Town picks up on wake (git-backed queue) |

## 8. Testing Strategy

| Layer | What |
|---|---|
| Unit | workstream handler (mock Gas Town HTTP), skills-sync generator output, trust-model `hermes` role mapping |
| Contract | golden-file MCP tool-def test: all pre-existing signatures byte-identical; only additive entries |
| Integration | LangGraph decision graph over remote-memory refs (Phase 2 clients); HITL interrupt/resume round-trip |
| E2E (staged) | M2 soak automation; M3 spawn→status→episode round-trip via `python -m clients.cli mcp test` |
| Audit | every M2/M3 flow produces DecisionLedger entries — verified by test + manual `journalctl`/ledger check |

---

## 9. Task Breakdown

**Milestones are sequential.** Each ends with deploy + verify before the next starts. Commit granularity: one task (or sub-task) per commit; submodule protocol as per the split plans.

### M1 — Flag-off the excluded subsystems
| ID | Task | Files | Verify |
|---|---|---|---|
| M1.1 | Disable in deploy env: `goal_dispatch_enabled=false`, `workflow_executor_enabled=false`, `langgraph_pipeline=false` (temporarily), proactivity surface flag off; add env flags for any excluded path lacking one (audit `xnch/main.py` scheduler block) | node-a env | chat + muse green; scheduler starts only non-excluded jobs |
| M1.2 | Regression pass: full `pytest`; e2e chat; confirm no excluded feature is user-visible | — | green |

### M2 — Hermes on node-b
| ID | Task | Files | Verify |
|---|---|---|---|
| M2.1 | Install Hermes; `infra/no-k3s/node-b/systemd/hermes.service` | infra + hermes docs | unit healthy; Hermes answers via LiteLLM :4000 |
| M2.2 | Actor registration: `hermes` → TRUSTED_AGENT in trust model; gateway auth flow for Hermes's MCP client | `xnch/security/trust_model.py` + auth path | Hermes tool call carries actor context; policy applies |
| M2.3 | Skills sync: `scripts/gen_agent_skills.py` emits SKILL.md per registry tool → Hermes skills dir | scripts + runbook | Hermes lists platform skills |
| M2.4 | Memory routing: add `hermes` to `deprecate_store_note_for` in deployed `memory-routing.yaml` | deploy config + `xnch/memory/routing_policy.py` default | `store_note` from hermes → deprecation error |
| M2.5 | Soak automation: one scheduled automation doing recall → governed exec → HITL approval → completion | muse + ledger | full chain in DecisionLedger |

### M3 — Gas Town on the Mac
| ID | Task | Files | Verify |
|---|---|---|---|
| M3.1 | Install Gas Town; launchd `com.xnch.gastown.plist`; workspace root init | Mac + `clients/` docs | gastown manages a test workspace |
| M3.2 | Gateway tools `xnch_workstream_spawn` (T2+HITL) + `xnch_workstream_status` (T0) | `xnch_mcp/handlers/workstream.py`, registry, tests | contract test shows additive-only registry diff |
| M3.3 | Outcome ingestion: completion → episode (type `workstream`) + audit event | handler + memory tools | `xnch_memory_recall` finds the outcome |
| M3.4 | Retire agent-runner (unload launchd; keep code until M5) | Mac | dispatch queue receives nothing; gastown active |

### M4 — LangGraph consolidation
| ID | Task | Files | Verify |
|---|---|---|---|
| M4.1 | Rebuild decision pipeline as first-class LangGraph graphs; HITL via `interrupt()` | `xnch/agents/pipeline_graph.py`, `pipeline_runtime.py` | graph tests; HITL resume round-trip |
| M4.2 | Relax Phase 2 guard: allow LangGraph with remote memory (refs); remove embedded-only guard | `xnch/main.py` guard + tests | graph runs with `XNCH_MEMORY_EMBEDDED=false` |
| M4.3 | `workstream_supervisor` graph (spawn decisions) | `xnch/agents/` | supervisor decides spawn from a chat turn |
| M4.4 | Proactivity surface re-target: `_memory_surface` reads automation/workstream episodes (flag-gated flip) | `xnch_mcp/handlers/memory.py` | muse surface shows agent activity |

### M5 — Delete the excluded code
| ID | Task | Files | Verify |
|---|---|---|---|
| M5.1 | Delete: `nexi/goal`, `nexi/proactivity`, `nexi/workflow`, `xnch/jobs/goal_dispatch.py`, `workflow_schedule.py`, `xnch/memory/workflow_store.py`, `agent_run_store.py`, `clients/agent-runner` | submodules + superrepo | grep clean; `pytest` green |
| M5.2 | Remove M1 flags + old proactivity path; update AGENTS.md Single-Home Registry (new homes: scheduling→Hermes, workstreams→Gas Town, graphs→LangGraph) + architecture docs | docs | review |
| M5.3 | Enable `langgraph_pipeline=true` as default; final e2e + audit verification; update this spec's status | config + docs | all success criteria demonstrated |

---

## 10. Risks & Mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Hermes bypasses bridge with local tools (browser/terminal) | Medium | its sandbox is node-b-scoped; anything touching platform data/memory/exec must go through `xnch_*` — enforced by policy + review of Hermes config; browser/terminal actions inside sandbox are acceptable scope |
| Hermes memory drift (scratch used as durable) | Medium | `deprecate_store_note_for` + am_* routing (M2.4); periodic audit |
| Gas Town project immaturity / API churn | Medium | only two thin tools depend on it; workspace state is git (worst case: manual recovery) |
| Mac sleeps mid-workstream | High | by design (burst tempo); git resume; Hermes never scheduled on Mac |
| Auth of Hermes at the MCP HTTP router | Medium | resolve at M2.2 (Open Question 1); must bind actor identity, no anonymous path |
| LangGraph rewrite scope creep | Medium | M4.1 rebuilds expression, not semantics; supervisor graph capped at one |
| 9 deployables > 6–8 envelope | Accepted | documented cost; hermes+gastown are the entire agentic layer |
| Trajectory quality for QLoRA | Unknown | governed-tool trajectories are clean by construction; validate with xnch-train Phase 0 gates |

## 11. Open Questions
1. **Hermes→gateway auth mechanism** (static gateway token vs signed short-lived tokens) — decide at M2.2; must present actor context.
2. **Gas Town reachability** — gateway→Mac direct POST over tailscale (recommended) vs Mac-side polling; decide at M3.1.
3. External channel (Telegram) — deferred; platform-only default is reversible.
4. Trajectory export cadence + filter criteria into `xnch-train` — decide after M2 soak produces real volumes.
