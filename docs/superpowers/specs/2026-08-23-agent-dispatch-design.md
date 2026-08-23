# Agent Dispatch — xnch drives coding agents (v0: opencode on Mac)

- **Date:** 2026-08-23
- **Status:** Approved in chat (ck-san), implementation starting
- **Scope:** v0 of the ACT half of the system loop — SENSE (session-ingest, specced separately) → THINK (goals/workflows/HITL, live) → **ACT (this spec)** → REPORT.

## Problem

xnch/nexi can govern and remember but cannot *do*: goal steps and workflow steps have no
executor that produces real artifacts. ck-san's coding agents (opencode, Claude Code,
Cursor) hold the heavy lifting capability under their own model quotas — the 24 GB local
GPU stays orchestrator/governor, not code factory. Missing piece: a governed way for
xnch to hand a task to opencode running on the Mac and get an outcome back.

## Decisions

1. **Pull, not push.** A resident runner on the Mac (`agent-runner`) claims dispatched
   tasks from xnch over HTTP. No sshd exposure, no inbound ports on the Mac; the runner
   is outbound-only, exactly like the muse web app. Auth = the shared `XNCH_GATEWAY_SECRET`
   muse already holds.
2. **Lease-based claiming**, cloned from the workflow executor pattern
   (`claim_next_approved_step(lease_owner, ttl_s)`): a claim marks the run `RUNNING` with
   a lease; only lease renewal/completion prevents another claimer from taking it. This
   makes runners swappable/addable later (node-a etc.) with zero design change.
3. **Human click = the approval.** Dispatch is triggered from muse by ck-san (gateway-token
   gated write). Deeper HITL per agent-action comes later via opencode permission config +
   xnch_mcp tools; v0 does not wrap agent internals.
4. **Workspace isolation:** every run executes in a fresh `~/xnch-agents/<run_id>/`
   directory. Headless runs never touch live repos uninvited.
5. **Transcript memory is free:** opencode persists sessions to its own store; the
   session-ingest job (separate approved spec) pulls them into episodic/Kuzu hourly. This
   spec adds no ingest code.

## Non-goals (v0)

Claude Code / Cursor adapters · scheduled auto-dispatch · nexi-decided dispatch ·
parallel run fan-out · streaming agent output into muse.

## API contract (xnch, gateway-token gated writes)

Table `agent_runs`:

```sql
CREATE TABLE IF NOT EXISTS agent_runs (
  id            TEXT PRIMARY KEY,
  status        TEXT NOT NULL CHECK (status IN ('QUEUED','RUNNING','DONE','FAILED','EXPIRED')),
  prompt        TEXT NOT NULL,
  workspace     TEXT NOT NULL,
  runner_id     TEXT,
  lease_expires_at REAL,
  exit_code     INTEGER,
  output_path   TEXT,
  error         TEXT,
  created_at    REAL NOT NULL,
  updated_at    REAL NOT NULL
);
```

Routes (mounted like workflows router):

| Route | Auth | Body | Effect |
|---|---|---|---|
| `POST /agents/dispatch` | gateway token | `{prompt, workspace?}` | creates run `QUEUED`, returns row |
| `POST /agents/dispatch/next` | gateway token | `{runner_id, ttl_s=1800}` (lease must outlive the worst-case agent run; no mid-run renewal in v0) | claims oldest QUEUED → `RUNNING` + lease; `204` if none |
| `POST /agents/runs/{id}/outcome` | gateway token | `{outcome_status: DONE\|FAILED, exit_code?, output_path?, error?, renew_lease?: bool}` | completes or extends lease |
| `GET /agents/runs` | open read | `?status=&limit=` | list runs |

Status machine: `QUEUED → RUNNING → DONE|FAILED`; a RUNNING run whose lease lapses
without outcome may be re-claimed (claimed again resets lease; v0 keeps same row).

## Mac runner (`agent-runner/`, top-level package)

- One file loop (~120 lines) + launchd plist; deps: `httpx` only.
- Config via env (`~/.xnch-agent-runner.env`): `XNCH_GATEWAY_URL`,
  `XNCH_GATEWAY_SECRET`, `XNCH_RUNNER_ID` (default hostname), `XNCH_AGENT_COMMAND`
  (default `opencode run [message..]`).
- Loop: claim (long-poll friendly 5 s sleep when 204) → mkdir workspace →
  `subprocess.run(shlex.split(command) + ["-p", prompt], cwd=workspace, timeout=XNCH_RUNNER_TIMEOUT_S default 1800)`
  → post outcome with captured exit code; exceptions → FAILED with error text.
- Launchd label `com.xnch.agent-runner`, KeepAlive=true, runs at load.

## muse UI

New `/agents` page (sidebar entry "Agents", Bot icon): dispatch form (prompt textarea,
optional workspace override) + run list cards with status pill, mirroring workflow-run
card UX. Writes go through the existing signed `/api/gateway` proxy.

## Testing

- Route tests mirror `test_workflow_routes.py`: create→list, claim semantics incl. lease
  exclusivity + 204 empty, outcome transitions, invalid token 401s, bad body 422s.
- Runner: offline unit test of command assembly; live smoke = dispatch a trivial prompt
  ("create hello.txt containing hi") end-to-end and verify artifact + DONE.
- E2E acceptance: Day-1 job-search task dispatched from muse, artifact lands in
  `~/xnch-agents/<id>/`, episode recorded, goal step-outcome posted manually after review.
