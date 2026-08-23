# XNCH Audit — Agentic Loop, HITL, Security Re-check

**Date:** 2026-08-22 · **Repo:** `xnchSystems/xnch` @ `3593184` (master) · ornith worktree @ `c26c413`
**Method:** code-review-graph rebuild at HEAD (780 nodes) + direct reads of `agents/`, `memory/goal_store.py`, `routes/{goals,execution,pipeline}.py`, `main.py`, `config.py`, and monorepo `scripts/agent-gateway/`. Prior-session memory had zero records of the earlier review, so nothing below takes any prior "fixed" label on faith.

---

## What's actually done vs. what's assumed done

| Piece | Claimed | Reality |
|---|---|---|
| Goal model | new Goal model | ✅ Done — `nexi/models/goal.py:19` (lives in nexi, not xnch; xnch routes return ad-hoc dicts) |
| GoalStore | durable store | ✅ Done — `xnch/memory/goal_store.py`: SQLite/aiosqlite, lease-based claim w/ TTL reclaim (`:51-66`), `max_steps`, consecutive-failure breaker (`:68-95`). Tests: `test_goal_store.py`, `test_goal_routes.py` |
| Scheduler | APScheduler-driven goal scheduling | ❌ **Not done.** APScheduler runs 4 learning cron jobs only (`xnch/main.py:152-159`). Nothing ever calls `claim_next_goal` — it's a manual endpoint (`routes/goals.py:83`). The autonomous loop cannot run unattended. |
| Circuit-breaker HITL gate | propose → interrupt → execute for looping goals | ⚠️ **Half done.** In-run EXECUTION interrupt works (`pipeline_graph.py:196-208`, `hitl.py:63-84`, mode-aware via `config.py:130-132`). But the *goal-level* loop is gated only by `failure_threshold=3 → FAILED`; goals never route through the HITL interrupt at all (goal advancement happens via `/execution/outcome` callback, bypassing the graph). Propose→interrupt→execute for looping goals: design-only. |
| Stub runner proving the loop | simulated tools before real ones | ✅ Done & clean — `routes/execution.py:30-35` deterministic SHA-256 outcome, `:48-68` override hook; zero subprocess/tool-adapter surface. `dispatch` node emits events only (`pipeline_graph.py:236-240`). Genuinely isolated. |
| LoongFlow loop | LangGraph replacement | ✅ Implemented behind `XNCH_LANGGRAPH_PIPELINE=true` (off by default — good), AsyncPostgresSaver checkpointer (`pipeline_runtime.py:55-71`), invoke/resume/pending API (`routes/pipeline.py`). Caveat: `assemble_context` passes all-`None` stores (`pipeline_graph.py:49-59`) — context is hollow in this path. |
| codegen_loop fix | credential re-scoping | ❌ **Moved, not fixed.** See F1. |
| Worktree isolation per agent | resolve FS races | ❌ Not present anywhere in-repo. Only deploy-time worktrees (`scripts/deploy.sh`) and one dev worktree (`/Users/xnch/xnch-ornith`). |

---

## Findings

### F1 · BLOCKER — Skip-permissions capability survived by relocation; no credential re-scoping
The known issue said the fix must be credential re-scoping, not flag removal. Reality: commit `f545682` deleted `agents/codegen_loop.py` ("moved out of repo") and re-scoped *actor roles* (`security/trust_model.py`, dropped `claude_code`/`openclaw`) — but the headless-execution capability now lives in `scripts/agent-gateway/` with a worse posture:

- `adapters/opencode.py:20-21` appends `--auto` whenever `opencode_auto_approve` is set — and it defaults to **True** (`config.py:24`). Auto-approved tool/headless execution is the same risk class as `--dangerously-skip-permissions`.
- `adapters/base.py:63-68` and `:107-112` spawn the CLI with a fully **inherited environment** — no env allowlist, no credential scoping. Every key in the gateway process env flows into each spawned agent.
- `main.py:39-41` — `_verify_api_key` **fails open**: with the default `api_key=None` (`config.py:13`) every request is allowed. So by default: unauthenticated HTTP service → spawns auto-approving CLI agent → inherits all credentials.
- Mitigating: bound to `127.0.0.1` by default (`config.py:11`); `cwd` comes from server settings only (`main.py:50-51`), not client input; timeouts kill children properly (`base.py:70-74`).

**Required:** default `opencode_auto_approve=False`; scrubbed env (allowlist) passed to `create_subprocess_exec`; fail-closed auth when `api_key` unset.

### F2 · HIGH — Core REST surface effectively unauthenticated
Only `chat.py:37-39` and `session.py` check Authorization. `TokenVerifier` is instantiated (`main.py:48`) but routers are mounted bare (`main.py:195-208`). Unauthenticated callers can: approve/reject HITL interrupts (`POST /governance/pipeline/resume`), record execution outcomes (`POST /execution/outcome` — drives goal advancement, `execution.py:101-105`), claim/create/cancel goals, hit admin/memory/policy routes. Acceptable for localhost dev; blocker before any network exposure.

### F3 · MEDIUM — Committed database credential
`xnch/config.py:67` hardcodes `postgresql://xnch:<password>@localhost:5432/xnch` as the settings default. Move to env-only with no default; rotate the leaked value (it's in git history).

### F4 · MEDIUM — Goal scheduler missing; loop can't run autonomously
No APScheduler job consumes due goals. `next_due_at`/lease machinery exists but is dead weight until something calls `/goals/claim` on a cadence. This was an explicit phase deliverable — still design-only.

### F5 · MEDIUM — HITL gate does not cover looping goals
Interrupt fires solely on `intent_class == "EXECUTION"` inside a single pipeline run (`pipeline_graph.py:196`). A goal that loops step-after-step via `/execution/outcome` never hits a human gate; its only stop condition is `consecutive_failures >= failure_threshold` (`goal_store.py:82-84`). A goal failing *slowly but successfully* (e.g., SUCCESS outcomes doing the wrong thing) runs to `max_steps` with zero oversight. Wire goal steps through the graph's interrupt, or add a per-goal approval counter.

### F6 · MEDIUM — Worktree isolation: unimplemented, race window open
No code creates or manages per-agent worktrees. The gateway runs every agent in one shared `settings.cwd`. Two concurrent agents on the same project will collide on files/locks/indexes. The stated mitigation strategy exists only in prose.

### F7 · LOW — LangGraph path context is hollow
`pipeline_graph.py:49-59` passes `working_memory/pg_episodic/graph_store/relationship_store/sensory_buffer = None` despite `create_pipeline(stores=...)` existing for injection. Decisions are made with empty episodic/entity context. Stub-acceptable now; track before real-tool wiring.

### F8 · LOW — Cross-package absolute imports violate conventions
All eight nodes import `from nexi.…` inside `xnch/agents/` (`pipeline_graph.py:20,49,74,100,134,169,225`). AGENTS.md forbids sibling-package absolute imports; this hard-couples xnch→nexi runtime layout and breaks if either package is installed standalone.

### F9 · LOW — Minor robustness nits
- `complete_step` read-modify-write isn't transaction-guarded (`goal_store.py:72-94`); fine under single-process leases, racy across processes (add WAL + `busy_timeout` or do it in one SQL statement).
- `progress` accumulates an unbounded string (`goal_store.py:87`).
- `/execution/execute` accepts an unvalidated `dict` body (`execution.py:49`).
- `_fire_nexi_callback` reads attributes that never exist on the model via `getattr` defaults (`execution.py:116-119`) — dead branches.

### F10 · INFO — Dependencies: accounted for, one packaging nit
Since last-review baseline `0bd17ad` (Aug 4): added `mcp`, `anyio`, `langgraph`, `langgraph-checkpoint-postgres`, `psycopg[binary]`, plus scraper/embedding stack (`trafilatura`, `markdownify`, `beautifulsoup4`, `crawlee`, `onnxruntime`, `numpy`, `tokenizers`). All are justified in-commit (HITL feature `d440606`/`e212d06`; scraper integration `13d75e5`) and annotated in `pyproject.toml`. Nit: the heavy scraper/embedding set belongs in an optional extra, not the core API-server dependency list — it inflates every deploy of the governance engine.

---

## Positive signals
- Execution stub is honestly a stub — no leaky abstraction to real tools found (grep for subprocess/shell in `xnch/` clean).
- Lease reclaim + terminal-state transitions in GoalStore are coherent; `--dangerously-skip-permissions` appears nowhere in either branch or the ornith worktree (verified by search).
- Resume API validates decision payloads strictly (`routes/pipeline.py:25-32`); dangerous flags (`hitl mode=never`) documented as test-only (`hitl.py:75`).
- Feature-flagged rollout (`langgraph_pipeline=false` default).

## Recommended order of attack
1. F1 (env allowlist + fail-closed auth + `opencode_auto_approve=False`) — small diffs, kills the blocker.
2. F3 rotate/remove hardcoded DSN; F2 add auth dependency to routers (one `include_router(..., dependencies=[...])` sweep).
3. F4+F5 together: scheduler job → claim → run step through pipeline so goals inherit the EXECUTION interrupt.
4. F7/F8/F6 before real-tool wiring.
