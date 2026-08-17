# Goal-Tracking Agentic Loop — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development (or executing-plans). Steps use `- [ ]` checkboxes.

**Goal:** Prove a self-directed goal loop — create → poll → plan → act (simulated) → observe → advance/replan → complete/fail/escalate — on the existing nexi pipeline + stub runner.

**Architecture:** Durable goals in a new `GoalStore` (xnch/SQLite). One serialized `goal_driver_loop` in nexi polls `claim_next_goal`, synthesizes a step input, and reuses the existing pipeline to plan + dispatch one action per step. The stub runner honors an in-band `simulation` override (deterministic hash default) and advances the goal in `execution_outcome` (xnch-side). Reflection keeps learning in the background.

**Tech Stack:** Python 3.13+, FastAPI, aiosqlite, httpx, Pydantic, asyncio. No new deps.

**Spec:** this plan (per the brief's DECIDED DIRECTIONS).

## Global Constraints

- Python 3.13+, async-first; deps limited to already-present aiosqlite/httpx/pydantic/fastapi.
- AGENTS.md: `StrEnum`, snake_case, `Annotated[T, Field(...)]`, lowercase generics, `BaseModel`, local relative imports, `_make_*` test helpers.
- Models in `nexi/models/`; stores in `xnch/memory/` (schema in `db.py`); adapters in `nexi/adapters/`; routes in `xnch/routes/`.
- P0: single serialized driver, 1–3 goals round-robin; additive to 10+ via the lease mechanism.
- `simulation` rides the existing dispatch payload; stub honors it, real runner ignores it later.
- Reuse the primary nexi pipeline; do NOT build on the dormant `xnch/agents/` LangGraph copy.

## File Structure

| File | Responsibility |
|---|---|
| `nexi/models/outcomes.py` (M) | add `simulation`, `goal_id` to `ExecutionDispatchPayload` |
| `nexi/models/goal.py` (C) | `GoalStatus`, `Goal` |
| `xnch/memory/db.py` (M) | `goals` table |
| `xnch/memory/goal_store.py` (C) | `GoalStore`: create/get/list/claim/complete_step/update |
| `xnch/routes/execution.py` (M) | `simulate_outcome`, stub override, goal advance |
| `xnch/routes/goals.py` (C) | goal endpoints |
| `nexi/adapters/xnch_client.py` (M) | `claim_next_goal`, `update_goal`, `submit_verdict(goal_id=…)` |
| `nexi/pipeline/dispatch.py` (M) | pass `simulation`/`goal_id` |
| `nexi/pipeline/run.py` (C) | `run_pipeline_pass` extracted from `session_start` |
| `nexi/main.py` (M) | `session_start` delegates; start `_goal_driver_loop` (gated) |
| `nexi/goal/planner.py`, `nexi/goal/driver.py` (C) | step synthesis + loop |
| `nexi/config.py` (M) | `goal_driver_enabled`, `goal_poll_interval_s`, `goal_default_max_steps`, `goal_default_failure_threshold` |

### Task 1 — Dispatch payload: `simulation` + `goal_id`

**Files:** Modify `nexi/models/outcomes.py`; Test `nexi/tests/test_outcome_models.py` (new)

**Produces:** `ExecutionDispatchPayload.simulation: dict[str, Any] | None = None`, `.goal_id: UUID | None = None`

- [ ] **Step 1: Write the failing test**

```python
# nexi/tests/test_outcome_models.py
from uuid import uuid4
from nexi.models.outcomes import ExecutionDispatchPayload

async def test_dispatch_payload_carries_simulation_and_goal_id():
    gid = uuid4()
    p = ExecutionDispatchPayload(
        trace_id=uuid4(), decision_id=uuid4(),
        action_spec={"type": "DEPLOY", "target": "x", "params": {}},
        execution_token="tok", token_ttl_ms=30000,
        simulation={"outcome": "fail", "detail": "x", "next_plan_hint": "y"},
        goal_id=gid,
    )
    assert p.simulation == {"outcome": "fail", "detail": "x", "next_plan_hint": "y"}
    assert p.goal_id == gid

async def test_dispatch_payload_defaults():
    p = ExecutionDispatchPayload(
        trace_id=uuid4(), decision_id=uuid4(),
        action_spec={}, execution_token="t", token_ttl_ms=1,
    )
    assert p.simulation is None and p.goal_id is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest nexi/tests/test_outcome_models.py -v`
Expected: FAIL — `simulation`/`goal_id` not accepted.

- [ ] **Step 3: Implement** — add `simulation: dict[str, Any] | None = None` and `goal_id: UUID | None = None` to `ExecutionDispatchPayload` (`nexi/models/outcomes.py:27`).

- [ ] **Step 4: Run test to verify it passes** — `pytest nexi/tests/test_outcome_models.py -v` → PASS

- [ ] **Step 5: Commit**

```bash
git add nexi/models/outcomes.py nexi/tests/test_outcome_models.py
git commit -m "feat(nexi): add simulation+goal_id to dispatch payload"
```

### Task 2 — `goals` table + `GoalStore`

**Files:** Modify `xnch/memory/db.py`; Create `xnch/memory/goal_store.py`; Test `xnch/tests/test_goal_store.py`

**Produces:** `GoalStore(db_path)` with `create_goal`, `get_goal`, `list_goals`, `claim_next_goal`, `complete_step`, `update_goal`

- [ ] **Step 1: Write the failing test** — `xnch/tests/test_goal_store.py` covering:

```python
from xnch.memory.db import init_db
from xnch.memory.goal_store import GoalStore

async def test_create_and_get(db_path): ...
async def test_claim_next_goal_marks_running(db_path): ...     # PENDING -> RUNNING, lease set
async def test_claim_returns_none_when_none_eligible(db_path): ...
async def test_complete_step_success_increments(db_path): ...  # steps+1, status ACTIVE if < max
async def test_complete_step_success_completes(db_path): ...   # steps >= max -> COMPLETED
async def test_complete_step_failure_threshold(db_path): ...   # consecutive -> FAILED at threshold
async def test_claim_skips_running_and_terminal(db_path): ...
```

Fixture uses `tmp_path` + `await init_db(path)` (mirror `xnch/tests/test_experience_store.py`).

- [ ] **Step 2: Run test to verify it fails** — `pytest xnch/tests/test_goal_store.py -v` → FAIL (module missing)

- [ ] **Step 3: Implement**

Add to `_SCHEMA` in `xnch/memory/db.py` (before `system_state`):

```sql
CREATE TABLE IF NOT EXISTS goals (
    goal_id             TEXT PRIMARY KEY,
    owner_actor_id      TEXT NOT NULL,
    objective           TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'PENDING',
    progress            TEXT NOT NULL DEFAULT '',
    steps_completed     INTEGER NOT NULL DEFAULT 0,
    max_steps           INTEGER NOT NULL DEFAULT 10,
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    failure_threshold   INTEGER NOT NULL DEFAULT 3,
    last_step_outcome   TEXT,
    next_due_at         REAL,
    lease_owner         TEXT,
    lease_expires_at    REAL,
    simulation_plan     TEXT,
    created_at          REAL NOT NULL DEFAULT (unixepoch()),
    updated_at          REAL NOT NULL DEFAULT (unixepoch()),
    schema_version      TEXT DEFAULT 'goal-v1'
);
CREATE INDEX IF NOT EXISTS idx_goals_due ON goals(status, next_due_at);
```

Create `xnch/memory/goal_store.py` mirroring `ExperienceStore` (aiosqlite, dict rows, no lazy schema needed since `init_db` owns DDL):

```python
"""Goal Store — durable, resumable goal state driving the agentic loop."""
import json
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

import aiosqlite

_ELIGIBLE = ("PENDING", "ACTIVE")
_TERMINAL = ("COMPLETED", "FAILED", "CANCELLED")


class GoalStore:
    def __init__(self, db_path: Path) -> None:
        self._db = db_path

    async def create_goal(
        self, *, owner_actor_id: str, objective: str,
        max_steps: int = 10, failure_threshold: int = 3,
        simulation_plan: list[dict[str, Any]] | None = None,
    ) -> str:
        goal_id = str(uuid4())
        now = time.time()
        async with aiosqlite.connect(self._db) as db:
            await db.execute(
                "INSERT INTO goals (goal_id, owner_actor_id, objective, status,"
                " max_steps, failure_threshold, next_due_at, simulation_plan,"
                " created_at, updated_at)"
                " VALUES (?, ?, ?, 'PENDING', ?, ?, ?, ?, ?, ?)",
                (goal_id, owner_actor_id, objective, max_steps, failure_threshold,
                 now, json.dumps(simulation_plan or []), now, now))
            await db.commit()
        return goal_id

    async def get_goal(self, goal_id: str) -> dict[str, Any] | None:
        async with aiosqlite.connect(self._db) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM goals WHERE goal_id = ?", (goal_id,)) as cur:
                row = await cur.fetchone()
        return dict(row) if row else None

    async def list_goals(self, status: str | None = None) -> list[dict[str, Any]]:
        q = "SELECT * FROM goals" + (" WHERE status = ?" if status else "") + " ORDER BY created_at"
        params = (status,) if status else ()
        async with aiosqlite.connect(self._db) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(q, params) as cur:
                return [dict(r) for r in await cur.fetchall()]

    async def claim_next_goal(self, lease_owner: str, lease_ttl_s: int = 120) -> dict[str, Any] | None:
        now = time.time()
        expires = now + lease_ttl_s
        async with aiosqlite.connect(self._db) as db:
            db.row_factory = aiosqlite.Row
            await db.execute(
                "UPDATE goals SET status='ACTIVE', lease_owner=NULL, lease_expires_at=NULL"
                " WHERE status='RUNNING' AND lease_expires_at < ?", (now,))
            async with db.execute(
                "UPDATE goals SET status='RUNNING', lease_owner=?, lease_expires_at=?, updated_at=?"
                " WHERE goal_id = (SELECT goal_id FROM goals WHERE status IN ('PENDING','ACTIVE')"
                " AND next_due_at <= ? ORDER BY next_due_at ASC LIMIT 1) RETURNING *",
                (lease_owner, expires, now, now)) as cur:
                row = await cur.fetchone()
            await db.commit()
        return dict(row) if row else None

    async def complete_step(self, goal_id: str, outcome_status: str) -> dict[str, Any] | None:
        now = time.time()
        async with aiosqlite.connect(self._db) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM goals WHERE goal_id = ?", (goal_id,)) as cur:
                row = await cur.fetchone()
            if not row:
                return None
            g = dict(row)
            steps = g["steps_completed"] + 1
            consecutive = g["consecutive_failures"]
            if outcome_status in ("SUCCESS", "PARTIAL"):
                consecutive = 0
                status = "COMPLETED" if steps >= g["max_steps"] else "ACTIVE"
            elif outcome_status == "FAILURE":
                consecutive += 1
                status = "FAILED" if consecutive >= g["failure_threshold"] else "ACTIVE"
            else:
                status = g["status"]
            progress = f"{g['progress']}\nstep {steps}: {outcome_status}".strip()
            await db.execute(
                "UPDATE goals SET status=?, progress=?, steps_completed=?, consecutive_failures=?,"
                " last_step_outcome=?, next_due_at=?, lease_owner=NULL, lease_expires_at=NULL,"
                " updated_at=? WHERE goal_id=?",
                (status, progress, steps, consecutive, outcome_status,
                 None if status in _TERMINAL else now, now, goal_id))
            await db.commit()
        return await self.get_goal(goal_id)

    async def update_goal(self, goal_id: str, *, status: str | None = None,
                          progress: str | None = None) -> dict[str, Any] | None:
        now = time.time()
        async with aiosqlite.connect(self._db) as db:
            if status is not None:
                await db.execute(
                    "UPDATE goals SET status=?, updated_at=?, lease_owner=NULL,"
                    " lease_expires_at=NULL WHERE goal_id=?", (status, now, goal_id))
            if progress is not None:
                await db.execute("UPDATE goals SET progress=?, updated_at=? WHERE goal_id=?",
                                 (progress, now, goal_id))
            await db.commit()
        return await self.get_goal(goal_id)
```

- [ ] **Step 4: Run test to verify it passes** — `pytest xnch/tests/test_goal_store.py -v` → PASS

- [ ] **Step 5: Commit**

```bash
git add xnch/memory/db.py xnch/memory/goal_store.py xnch/tests/test_goal_store.py
git commit -m "feat(xnch): goal store with atomic claim + step advancement"
```

### Task 3 — Simulation engine + goal advance

**Files:** Modify `xnch/routes/execution.py`; Test `xnch/tests/test_execution_simulation.py`

**Produces:** `simulate_outcome(action_type, params) -> str`; `execute_stub` resolves override/hash; `ExecutionOutcomeRequest.goal_id`; `execution_outcome` advances goal.

- [ ] **Step 1: Write the failing test**

```python
# xnch/tests/test_execution_simulation.py
from xnch.routes.execution import simulate_outcome

async def test_simulate_default_is_deterministic():
    assert simulate_outcome("DEPLOY", {"x": 1}) == simulate_outcome("DEPLOY", {"x": 1})

async def test_simulate_default_in_success_failure():
    assert simulate_outcome("DEPLOY", {"x": 1}) in ("SUCCESS", "FAILURE")
```

Plus (using `AsyncMock`/`MagicMock`, mirroring `xnch/tests/test_execution_callback.py`): `execute_stub` with `simulation={"outcome": "fail"}` posts `outcome_status="FAILURE"`; with no `simulation` posts the hash result; and `execution_outcome` with `goal_id` calls `app.goal_store.complete_step(goal_id, status)`.

- [ ] **Step 2: Run test to verify it fails** — `pytest xnch/tests/test_execution_simulation.py -v` → FAIL

- [ ] **Step 3: Implement** in `xnch/routes/execution.py`:

```python
import hashlib

def simulate_outcome(action_type: str, params: dict[str, Any]) -> str:
    digest = hashlib.sha256(
        json.dumps({"action_type": action_type, "params": params}, sort_keys=True).encode()
    ).hexdigest()
    return "SUCCESS" if int(digest[:2], 16) % 2 == 0 else "FAILURE"

class ExecutionOutcomeRequest(BaseModel):
    ...          # existing fields
    goal_id: str = ""

@router.post("/execute")
async def execute_stub(body: dict[str, Any], request: Request) -> dict[str, Any]:
    action_spec = body.get("action_spec") or {}
    sim = body.get("simulation") or {}
    status = sim.get("outcome") or simulate_outcome(
        action_spec.get("type", ""), action_spec.get("params", {}) or {})
    outcome = ExecutionOutcomeRequest(
        execution_ref=str(body.get("execution_ref", "")),
        decision_id=str(body.get("decision_id", "")),
        execution_token_ref=str(body.get("execution_token", "")),
        outcome_status=status,
        goal_id=str(body.get("goal_id") or ""),
        duration_ms=50,
    )
    return await execution_outcome(outcome, request)
```

and in `execution_outcome`, after the episode write + `_fire_nexi_callback`:

```python
    if body.goal_id:
        try:
            await app.goal_store.complete_step(body.goal_id, body.outcome_status)
        except Exception as exc:
            logger.error("goal advance failed (goal_id=%s): %s", body.goal_id, exc)
```

- [ ] **Step 4: Run test to verify it passes** — `pytest xnch/tests/test_execution_simulation.py -v` → PASS

- [ ] **Step 5: Commit**

```bash
git add xnch/routes/execution.py xnch/tests/test_execution_simulation.py
git commit -m "feat(xnch): simulated execution + goal advancement on outcome"
```

### Task 4 — `dispatch_execution` carries `simulation` + `goal_id`

**Files:** Modify `nexi/pipeline/dispatch.py`; Test `nexi/tests/test_dispatch.py` (new)

**Produces:** `dispatch_execution(..., simulation=None, goal_id=None)`

- [ ] **Step 1: Write the failing test** — mock `httpx.AsyncClient`; call `dispatch_execution(...)` with `simulation`/`goal_id`; assert POSTed JSON carries `payload.simulation` and `payload.goal_id`.

- [ ] **Step 2: Run test to verify it fails** — `pytest nexi/tests/test_dispatch.py -v` → FAIL

- [ ] **Step 3: Implement** — add `simulation: dict[str, Any] | None = None` and `goal_id: UUID | None = None` kwargs; pass through to `ExecutionDispatchPayload`; forward `goal_id` in `_record_stub_outcome`'s `/execution/outcome` JSON too.

- [ ] **Step 4: Run test to verify it passes** → PASS

- [ ] **Step 5: Commit** — `git commit -m "feat(nexi): dispatch passes simulation + goal_id"`

### Task 5 — Goal models

**Files:** Create `nexi/models/goal.py`; Modify `nexi/models/__init__.py`; Test `nexi/tests/test_goal_models.py`

**Produces:** `GoalStatus`, `Goal`

- [ ] **Step 1: Write the failing test** — validate `Goal(objective="deploy media service", owner_actor_id="agent")`; defaults `max_steps==10`, `failure_threshold==3`, `status==PENDING`; `model_dump(mode="json")` serializes `status` as a string.

- [ ] **Step 2: Run test to verify it fails** → FAIL

- [ ] **Step 3: Implement**

```python
# nexi/models/goal.py
import time
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class GoalStatus(StrEnum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    RUNNING = "RUNNING"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class Goal(BaseModel):
    goal_id: UUID = Field(default_factory=uuid4)
    owner_actor_id: str
    objective: str
    status: GoalStatus = GoalStatus.PENDING
    progress: str = ""
    steps_completed: int = 0
    max_steps: int = 10
    consecutive_failures: int = 0
    failure_threshold: int = 3
    last_step_outcome: str | None = None
    next_due_at: float | None = None
    lease_owner: str | None = None
    lease_expires_at: float | None = None
    simulation_plan: list[dict[str, Any]] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
```

Add `Goal`, `GoalStatus` to `nexi/models/__init__.py` imports + `__all__`.

- [ ] **Step 4: Run test to verify it passes** → PASS

- [ ] **Step 5: Commit** — `git commit -m "feat(nexi): goal models"`

### Task 6 — `XnchClient` goal methods

**Files:** Modify `nexi/adapters/xnch_client.py`; Test `nexi/tests/test_goal_client.py` (new)

**Produces:** `claim_next_goal(lease_owner) -> Goal | None`, `update_goal(goal_id, *, status=None, progress=None) -> Goal`, `submit_verdict(..., goal_id=None)`

- [ ] **Step 1: Write the failing test** — mock `self._http.post`; assert `/goals/claim` + `/goals/{id}/update` URL shapes; assert parsed `Goal`. Also assert `submit_verdict` body includes `goal_id` in `context` when provided.

- [ ] **Step 2: Run test to verify it fails** → FAIL

- [ ] **Step 3: Implement** — two HTTP methods using `Goal.model_validate(resp.json())`; thread `goal_id` into `submit_verdict`'s `context` dict (so `verdict.py:127` persists it in the episode `context_snapshot`).

- [ ] **Step 4: Run test to verify it passes** → PASS

- [ ] **Step 5: Commit** — `git commit -m "feat(nexi): xnch client goal methods"`

### Task 7 — Goal routes + wiring

**Files:** Create `xnch/routes/goals.py`; Modify `xnch/routes/__init__.py` + `xnch/main.py`; Test `xnch/tests/test_goal_routes.py`

**Produces:** `POST /goals`, `GET /goals`, `GET /goals/{goal_id}`, `POST /goals/claim`, `POST /goals/{goal_id}/step-outcome`, `POST /goals/{goal_id}/cancel` backed by `app.state.goal_store`.

- [ ] **Step 1: Write the failing test** — build a minimal FastAPI app with the router + `MagicMock` `goal_store`; exercise each endpoint's request/response shape.

- [ ] **Step 2: Run test to verify it fails** → FAIL

- [ ] **Step 3: Implement** — routes + register in `xnch/routes/__init__.py` (`goal_router`); in `xnch/main.py` lifespan add `s.goal_store = GoalStore(settings.db_path)` after `s.experience_store`, and `app.include_router(goal_router)`.

- [ ] **Step 4: Run test to verify it passes** → PASS

- [ ] **Step 5: Commit** — `git commit -m "feat(xnch): goal CRUD + claim endpoints"`

### Task 8 — Extract `run_pipeline_pass`

**Files:** Create `nexi/pipeline/run.py`; Modify `nexi/main.py`; Test `nexi/tests/test_pipeline_pass.py` (new)

**Produces:** `PipelinePassResult`, `run_pipeline_pass(*, xnch, model_adapter, policy_filter, intent_interpreter, session, raw_input, simulation=None, goal_id=None)`

- [ ] **Step 1: Write the failing test** — with mocked `XnchClient`/`ModelAdapter`/`PolicyFilter`/`IntentInterpreter`: (a) canned intent/options/verdict → `status="EXECUTING"` with `execution_ref` set, `dispatch_execution` called with `simulation`/`goal_id`; (b) `PolicyFilter.filter` raises `AllOptionsBlocked` → `status="ESCALATED"`.

- [ ] **Step 2: Run test to verify it fails** → FAIL

- [ ] **Step 3: Implement** — move steps 3–11 out of `nexi/main.py:session_start` (interpret → load_context → get_weight_config → generate_options → filter → score+simulate → select → compile → submit_verdict → dispatch). Map `AllOptionsBlocked` / `decision.escalation_triggered` / `verdict=="BLOCK"` → `PipelinePassResult(status="ESCALATED", hold_id=…)`; else `EXECUTING`. Keep STALE_SESSION retry. Refactor `session_start` to delegate + translate to `SessionStartResponse`.

- [ ] **Step 4: Run tests** — `pytest nexi/tests/test_pipeline_pass.py nexi/tests/test_session_flow.py -v` → PASS (session_flow guards the refactor)

- [ ] **Step 5: Commit** — `git commit -m "refactor(nexi): extract run_pipeline_pass for reuse"`

### Task 9 — Planner

**Files:** Create `nexi/goal/planner.py`; Test `nexi/tests/test_goal_planner.py`

**Produces:** `build_step_input(goal: dict) -> str`, `build_simulation(goal: dict) -> dict | None`

- [ ] **Step 1: Write the failing test** — `build_step_input` includes objective + progress + last `next_plan_hint`; `build_simulation` returns `simulation_plan[steps_completed]` when present, else `None`.

- [ ] **Step 2: Run test to verify it fails** → FAIL

- [ ] **Step 3: Implement** (pure functions, no I/O):

```python
# nexi/goal/planner.py
def build_step_input(goal: dict) -> str:
    base = goal.get("objective", "")
    progress = (goal.get("progress") or "").strip()
    hint = (goal.get("last_simulation") or {}).get("next_plan_hint") if goal.get("last_simulation") else None
    parts = [base]
    if progress:
        parts.append(f"[progress]\n{progress}")
    if hint:
        parts.append(f"[hint]\n{hint}")
    return "\n".join(parts)

def build_simulation(goal: dict) -> dict | None:
    plan = goal.get("simulation_plan") or []
    idx = goal.get("steps_completed", 0)
    return plan[idx] if idx < len(plan) else None
```

(Note: `next_plan_hint` is written into `progress` by the driver in Task 10; `build_step_input` folds `progress` in. The `last_simulation` accessor above is illustrative — the driver may instead persist the hint into `progress` and drop this branch.)

- [ ] **Step 4: Run test to verify it passes** → PASS

- [ ] **Step 5: Commit** — `git commit -m "feat(nexi): goal step planner"`

### Task 10 — Driver loop + wiring

**Files:** Create `nexi/goal/driver.py`; Modify `nexi/main.py` + `nexi/config.py`; Test `nexi/tests/test_goal_driver.py`

**Produces:** `goal_driver_loop(...)`; `_goal_driver_loop` asyncio task in nexi lifespan (gated by `NEXI_GOAL_DRIVER_ENABLED`)

- [ ] **Step 1: Write the failing test** — drive `_run_goal_step` with mocked `xnch`/pipeline/planner: (a) non-EXECUTING result → `update_goal(status="BLOCKED")`; (b) `goal_driver_loop` calls `claim_next_goal` repeatedly and stops when it returns `None` (use a bounded fake clock and a sentinel to exit).

- [ ] **Step 2: Run test to verify it fails** → FAIL

- [ ] **Step 3: Implement** `nexi/goal/driver.py`:

```python
import asyncio
import logging
from uuid import UUID

from nexi.config import settings
from nexi.models import SessionContext, Actor, ActorRole
from nexi.pipeline.run import run_pipeline_pass
from .planner import build_step_input, build_simulation

logger = logging.getLogger(__name__)
_LEASE_OWNER = "nexi-goal-driver"


def _make_goal_session() -> SessionContext:
    from uuid import uuid4
    return SessionContext(
        session_id=uuid4(), trace_id=uuid4(),
        actor=Actor(id="agent", role=ActorRole.AGENT,
                    capability_set=["READ", "QUERY", "DEPLOY"]),
        system_state_version="", policy_version="", idempotency_key=uuid4(),
        raw_input="", priority="NORMAL",
    )


async def _run_goal_step(goal, *, xnch, model_adapter, policy_filter, intent_interpreter) -> None:
    result = await run_pipeline_pass(
        xnch=xnch, model_adapter=model_adapter, policy_filter=policy_filter,
        intent_interpreter=intent_interpreter, session=_make_goal_session(),
        raw_input=build_step_input(goal),
        simulation=build_simulation(goal),
        goal_id=UUID(goal["goal_id"]),
    )
    if result.status != "EXECUTING":
        await xnch.update_goal(goal["goal_id"], status="BLOCKED",
                               progress=f"blocked: {result.status}")


async def goal_driver_loop(*, xnch, model_adapter, policy_filter, intent_interpreter) -> None:
    while True:
        await asyncio.sleep(settings.goal_poll_interval_s)
        try:
            goal = await xnch.claim_next_goal(_LEASE_OWNER)
        except Exception as exc:
            logger.warning("goal claim failed: %s", exc)
            continue
        if goal is None:
            continue
        try:
            await _run_goal_step(goal, xnch=xnch, model_adapter=model_adapter,
                                 policy_filter=policy_filter, intent_interpreter=intent_interpreter)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("goal step failed (goal=%s): %s", goal["goal_id"], exc)
            await xnch.update_goal(goal["goal_id"], status="ACTIVE")  # resumable
```

Wire in `nexi/main.py` lifespan (after `_reflector`), guarded:

```python
    goal_task: asyncio.Task | None = None
    if settings.goal_driver_enabled:
        goal_task = asyncio.get_running_loop().create_task(
            goal_driver_loop(xnch=_xnch, model_adapter=_model_adapter,
                             policy_filter=_policy_filter, intent_interpreter=_intent_interpreter))
```

cancel in shutdown (mirror `capability_task`). Add to `nexi/config.py`:

```python
    goal_driver_enabled: bool = False
    goal_poll_interval_s: int = 5
    goal_default_max_steps: int = 10
    goal_default_failure_threshold: int = 3
```

- [ ] **Step 4: Run test to verify it passes** → PASS

- [ ] **Step 5: Commit** — `git commit -m "feat(nexi): goal driver loop (gated)"`

### Task 11 — End-to-end proof

**Files:** Test `tests/test_goal_loop_e2e.py`

**Produces:** loop proof: COMPLETED / FAILED / BLOCKED.

- [ ] **Step 1: Write the failing test** — in-process FastAPI app with goal router + `execute_stub` + real `GoalStore(tmp_path)` + `AsyncMock` pipeline. Assert: (a) `simulation_plan=[success]*N`, `max_steps=3` → COMPLETED; (b) `[fail,fail,fail]`, threshold 3 → FAILED; (c) pipeline raises `AllOptionsBlocked` → BLOCKED. Drive claim→step→complete directly (no real LLM/network).

- [ ] **Step 2: Run test to verify it fails** → FAIL

- [ ] **Step 3: Implement** — iterate until green.

- [ ] **Step 4: Run test to verify it passes** → PASS

- [ ] **Step 5: Commit** — `git commit -m "test: goal loop e2e (complete/fail/block)"`

## Self-review

- **Coverage:** goal store ✓ T2, driver ✓ T10, simulation ✓ T3, e2e loop ✓ T11; no scheduler/budget (deferred) ✓; primary pipeline reused ✓; goal advancement xnch-side ✓; single serialized driver ✓.
- **Type consistency:** `GoalStatus`/`Goal`/`complete_step`/`claim_next_goal`/`update_goal`/`run_pipeline_pass`/`build_step_input`/`build_simulation` used consistently.
- **Actor identity:** `agent` actor (`xnch/auth/governance.py:15`) resolves for goal steps ✓.

## P1/P2 (roadmap only)

- **P1:** `plans` table + `PlanStore` + `plan_id` threading; real tool registry + code-driven dispatcher behind `/execute` (ornith probe first); proactivity-trigger→goal; graduated autonomy ladder; `GoalBudget` slot between claim and step.
- **P2:** reflection-derived subgoals; LLM-driven tool selection (probe-gated); weight/policy evolvers on goal-derived episodes.
