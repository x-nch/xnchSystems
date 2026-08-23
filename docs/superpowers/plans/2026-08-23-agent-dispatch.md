# Agent Dispatch v0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox syntax.

**Goal:** xnch exposes a governed dispatch queue; a Mac-side runner claims tasks and executes them headless in opencode; muse shows runs.

**Architecture:** Pull model — `agent-runner` polls xnch for QUEUED runs using the same lease pattern as the workflow executor. Three REST routes clone `routes/workflows.py` conventions (aiosqlite store, gateway-token gated writes). Transcript memory stays free via session-ingest.

**Tech Stack:** Python 3.13+, FastAPI, aiosqlite (xnch); stdlib-only Python (urllib/subprocess) runner; Next.js client components + signed `/api/gateway` proxy.

**Spec:** `docs/superpowers/specs/2026-08-23-agent-dispatch-design.md`

## Global Constraints

- xnch submodule branch `feat/agent-dispatch` cut from deployed pin 2380a62.
- All agent write routes use `require_gateway_access` exactly as routes/workflows.py does.
- Runner is stdlib-only; no pip installs on the Mac.
- Runs execute in `~/xnch-agents/<run_id>/`, never live repos.
- Status machine QUEUED -> RUNNING -> DONE|FAILED; expired-lease RUNNING rows are re-claimable.
- Repo conventions: modern unions, Pydantic wire models, snake_case, module docstrings, `_make_*` test helpers.

---

### Task 1: xnch — agent_runs table + AgentRunStore

**Files:**
- Modify: `memory/db.py` (append DDL after approvals block)
- Create: `memory/agent_run_store.py`
- Test: `tests/test_agent_run_store.py`
(all paths relative to xnch submodule root)

**Interfaces (produced):**
`AgentRunStore(db_path: Path)`:
- `async create_run(prompt: str, workspace: str) -> dict`  # status QUEUED
- `async claim_next(runner_id: str, ttl_s: int) -> dict | None`  # oldest QUEUED -> RUNNING + lease_expires_at=now+ttl; also re-claims expired RUNNING
- `async complete_run(run_id: str, *, outcome_status: str, exit_code: int | None = None, output_path: str | None = None, error: str | None = None) -> dict | None`  # None if missing or not RUNNING
- `async list_runs(status: str | None = None, limit: int = 50) -> list[dict]`
- `async get_run(run_id: str) -> dict | None`

DDL:
```sql
CREATE TABLE IF NOT EXISTS agent_runs (
    id               TEXT PRIMARY KEY,
    status           TEXT NOT NULL CHECK (status IN ('QUEUED','RUNNING','DONE','FAILED')),
    prompt           TEXT NOT NULL,
    workspace        TEXT NOT NULL,
    runner_id        TEXT,
    lease_expires_at REAL,
    exit_code        INTEGER,
    output_path      TEXT,
    error            TEXT,
    created_at       REAL NOT NULL DEFAULT (unixepoch()),
    updated_at       REAL NOT NULL DEFAULT (unixepoch())
);
CREATE INDEX IF NOT EXISTS idx_agent_runs_status ON agent_runs(status, created_at);
```

Steps:
- [ ] 1.1 Write failing tests: create defaults; FIFO claim sets RUNNING+runner+lease; claim returns None when only unexpired RUNNING exists; expired-lease RUNNING is re-claimable; complete_run DONE writes fields; complete on QUEUED returns None; list filter by status
- [ ] 1.2 Run pytest tests/test_agent_run_store.py -v -> FAIL (module missing)
- [ ] 1.3 Implement DDL in db.py init_db + store class mirroring WorkflowStore style
- [ ] 1.4 Tests PASS
- [ ] 1.5 Commit feat(agents): agent_runs store + schema

### Task 2: xnch — routes + wiring

**Files:**
- Create: `models/agent.py` — AgentDispatchRequest{prompt: Annotated[str, Field(min_length=1, max_length=20000)], workspace: str | None}, AgentClaimRequest{runner_id: str, ttl_s: int = 1800}, AgentOutcomeRequest{outcome_status: Literal["DONE","FAILED"], exit_code: int | None, output_path: str | None, error: str | None}
- Create: `routes/agents.py` — router prefix /agents
- Modify: `routes/__init__.py` export agents_router; `main.py` lifespan store init + include_router (~line 62 and ~249)
- Test: `tests/test_agent_routes.py`

Routes:
- POST /agents/dispatch (gateway token, 201) {prompt, workspace?} -> row; workspace default "~/xnch-agents/<id>" generated server-side when omitted
- POST /agents/dispatch/next (gateway token) {runner_id, ttl_s} -> 200 row | 204
- POST /agents/runs/{id}/outcome (gateway token) -> 200 row | 404 unknown | 409 not-RUNNING
- GET /agents/runs?status=&limit= (open read)

Steps:
- [ ] 2.1 Failing route tests using test_workflow_routes.py loader pattern (_load fresh modules, minimal app with state.agent_run_store + state.gateway_secret)
- [ ] 2.2 FAIL verify
- [ ] 2.3 Implement models + routes importing require_gateway_access from routes.workflows
- [ ] 2.4 Route tests PASS + pytest tests -q full suite green
- [ ] 2.5 Commit feat(agents): dispatch/claim/outcome routes

### Task 3: Mac runner package (main repo)

**Files:**
- Create: `agent-runner/xnch_agent_runner/{__init__.py, runner.py, __main__.py}`
- Create: `agent-runner/com.xnch.agent-runner.plist`, `agent-runner/README.md`
- Test: `tests/test_agent_runner_unit.py`

Config env: XNCH_GATEWAY_URL (default http://192.168.1.10:8001), XNCH_GATEWAY_SECRET (required), XNCH_RUNNER_ID (default hostname), XNCH_AGENT_COMMAND (default "opencode"), XNCH_AGENT_ARGS (default "run"), XNCH_RUNNER_TIMEOUT_S (default 1800), XNCH_RUNNER_POLL_S (default 5).

runner.py contract:
- `build_claim_payload(runner_id, ttl_s) -> bytes` (json)
- `post_json(url, payload, secret) -> tuple[int, dict]` urllib-based; returns (status, body)
- `build_command(cfg, prompt) -> list[str]` = shlex split command+args + ["-p", prompt]
- `handle_once(cfg) -> str` one poll cycle: claim -> 204 "empty" | spawn subprocess.run(cwd=expanduser(workspace), timeout) -> outcome DONE (exit 0) else FAILED w/ stderr tail -> "done"/"failed"
- `main()` loop with sleep POLL_S between empties

plist: Label com.xnch.agent-runner, ProgramArguments [/usr/bin/env, python3, -m, xnch_agent_runner], WorkingDirectory ~/xnch-agents, EnvironmentVariables placeholders for the env vars, KeepAlive true, RunAtLoad true, StandardOut/ErrorPath ~/xnch-agents/runner.log

Steps:
- [ ] 3.1 Failing unit tests: build_command assembly incl quoting; post_json against a local http.server fixture (200 json, 204); handle_once DONE path using monkeypatched spawn
- [ ] 3.2 FAIL verify
- [ ] 3.3 Implement
- [ ] 3.4 PASS
- [ ] 3.5 Commit feat(agent-runner): stdlib dispatch runner + launchd template

### Task 4: muse /agents page

**Files:**
- Create: `web/src/lib/api/agents.ts` — types AgentRun; fns dispatchAgent(prompt, workspace?), listAgentRuns() via fetch("/api/gateway/agents/...")
- Create: `web/src/app/agents/page.tsx` — client page: form (prompt textarea + optional workspace) + run cards (prompt excerpt, status pill, runner, timestamps), 5s polling refresh, same visual language as workflows page
- Modify: `web/src/components/layout/sidebar.tsx` NAV += { href: "/agents", label: "Agents", icon: Bot }
- Modify: `web/src/app/api/gateway/[...path]/route.ts` GATED_PREFIXES += "agents"

Steps:
- [ ] 4.1 api lib + page + sidebar + gated prefix
- [ ] 4.2 npm run build && npx vitest run green (4/4 existing still pass)
- [ ] 4.3 Manual smoke against prod gateway
- [ ] 4.4 Commit feat(muse): agents page + gated prefix

### Task 5: deploy + e2e

Steps:
- [ ] 5.1 Push xnch feat/agent-dispatch; merge into master superproject ptr flow (same as PR5 resolution): bump ptr commit in main repo master, push, pull on node-a, submodule update, restart xnch.service
- [ ] 5.2 Install runner on Mac: mkdir ~/xnch-agents; write plist with real secret from web/.env.local into ~/Library/LaunchAgents; launchctl load; verify log shows poll cycle
- [ ] 5.3 E2E smoke: curl POST /agents/dispatch {"prompt":"Create hello.txt containing exactly: hi"} -> runner claims -> opencode run -> DONE + artifact check
- [ ] 5.4 Real task: Day-1 job goal dispatch after intake answers exist
- [ ] 5.5 Commit any deploy fixes; update AGENTS.md dev commands if needed
