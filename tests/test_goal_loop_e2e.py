"""End-to-end proof of the goal-tracking agentic loop (no LLM / no network).

Drives the real ``GoalStore`` + ``execute_stub`` → ``execution_outcome`` path and
the nexi goal driver's ``_run_goal_step`` to verify the three terminal states:

* ``COMPLETED`` — a simulation plan of N successes reaches ``max_steps``;
* ``FAILED``    — repeated failures cross ``failure_threshold``;
* ``BLOCKED``   — a pipeline pass that escalates marks the goal BLOCKED.

All LLM and network I/O is stubbed out: ``execute_stub`` resolves a
``simulation`` override (never the deterministic hash, never an LLM), the
nexi callback is a no-op, and the pipeline pass is a mock returning
``ESCALATED`` for the block test.
"""
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

from nexi.goal.driver import _run_goal_step
from nexi.models import Goal
from nexi.pipeline.run import PipelinePassResult
from xnch.memory.db import init_db
from xnch.memory.goal_store import GoalStore
from xnch.routes.execution import execute_stub


def _make_request(goal_store: GoalStore) -> MagicMock:
    """Build a MagicMock Request whose app.state carries the stores the
    execution_outcome path touches (mirrors test_execution_callback.py)."""
    request = MagicMock()
    state = request.app.state
    state.episodic = MagicMock()
    state.episodic.complete_episode = AsyncMock(return_value="ep-e2e")
    state.pg_episodic = MagicMock()
    state.pg_episodic.complete_decision_episode = AsyncMock(return_value=None)
    state.event_log = MagicMock()
    state.goal_store = goal_store
    return request


def _make_dispatch_body(goal_id: str, *, step: int, outcome: str) -> dict[str, object]:
    """Build the /execute dispatch body for one loop iteration."""
    return {
        "execution_ref": f"ref-{step}",
        "decision_id": f"dec-{step}",
        "execution_token": "t",
        "action_spec": {"type": "DEPLOY", "target": "svc", "params": {}},
        "goal_id": goal_id,
        "simulation": {"outcome": outcome},
    }


async def test_goal_loop_completes(tmp_path: Path) -> None:
    """A simulation plan of 3 successes completes the goal at max_steps=3."""
    db_path = tmp_path / "goal_loop.db"
    await init_db(db_path)
    store = GoalStore(db_path)
    goal_id = await store.create_goal(
        owner_actor_id="e2e",
        objective="deploy service",
        max_steps=3,
        simulation_plan=[{"outcome": "success"}, {"outcome": "success"}, {"outcome": "success"}],
    )
    request = _make_request(store)
    with patch("xnch.routes.execution._fire_nexi_callback", new=AsyncMock()):
        for step in range(3):
            goal = await store.claim_next_goal("e2e")
            assert goal is not None
            body = _make_dispatch_body(str(goal["goal_id"]), step=step, outcome="success")
            await execute_stub(body, request)
        await asyncio.sleep(0)  # drain the fire-and-forget callback task

    goal = await store.get_goal(goal_id)
    assert goal is not None
    assert goal["status"] == "COMPLETED"
    assert goal["steps_completed"] == 3


async def test_goal_loop_fails_on_repeated_failure(tmp_path: Path) -> None:
    """Three consecutive failures cross failure_threshold=3 → FAILED."""
    db_path = tmp_path / "goal_loop.db"
    await init_db(db_path)
    store = GoalStore(db_path)
    goal_id = await store.create_goal(
        owner_actor_id="e2e",
        objective="deploy service",
        max_steps=10,
        failure_threshold=3,
        simulation_plan=[{"outcome": "fail"}, {"outcome": "fail"}, {"outcome": "fail"}],
    )
    request = _make_request(store)
    with patch("xnch.routes.execution._fire_nexi_callback", new=AsyncMock()):
        for step in range(3):
            goal = await store.claim_next_goal("e2e")
            assert goal is not None
            body = _make_dispatch_body(str(goal["goal_id"]), step=step, outcome="fail")
            await execute_stub(body, request)
        await asyncio.sleep(0)  # drain the fire-and-forget callback task

    goal = await store.get_goal(goal_id)
    assert goal is not None
    assert goal["status"] == "FAILED"
    assert goal["consecutive_failures"] == 3


async def test_goal_loop_blocks_on_escalation(tmp_path: Path) -> None:
    """A pipeline pass returning ESCALATED marks the goal BLOCKED."""
    db_path = tmp_path / "goal_loop.db"
    await init_db(db_path)
    store = GoalStore(db_path)
    goal_id = await store.create_goal(
        owner_actor_id="e2e",
        objective="deploy service",
        max_steps=3,
    )
    row = await store.get_goal(goal_id)
    assert row is not None
    goal = Goal(
        owner_actor_id=row["owner_actor_id"],
        objective=row["objective"],
        goal_id=UUID(row["goal_id"]),
    )

    xnch = MagicMock()
    xnch.get_system_state = AsyncMock(
        return_value={"system_state_version": "v1", "policy_version": "v1"}
    )
    xnch.update_goal = AsyncMock()

    with patch(
        "nexi.goal.driver.run_pipeline_pass",
        new=AsyncMock(return_value=PipelinePassResult(status="ESCALATED")),
    ):
        await _run_goal_step(
            goal,
            xnch=xnch,
            model_adapter=None,
            policy_filter=None,
            intent_interpreter=None,
        )

    xnch.update_goal.assert_awaited_once()
    assert xnch.update_goal.call_args.kwargs["status"] == "BLOCKED"
