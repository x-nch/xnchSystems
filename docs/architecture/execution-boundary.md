# Execution Boundary: xnch vs nexi

## The rule
nexi owns DECIDING (the 12-step pipeline that turns a user turn into an action
spec). xnch owns ORCHESTRATING (scheduling crons, dispatching to runners,
HITL approvals, gateway/API surface).

## Verified boundaries

| Subsystem | Owner | Key file:line | Why it belongs there | Confirmed callers |
|---|---|---|---|---|
| Intent interpretation (LangGraph node) | shared (nexi impl) | `xnch/agents/pipeline_graph.py:35` → `nexi/pipeline/intent_interpreter.py:IntentInterpreter.interpret` | Node is a LangGraph wrapper around nexi's canonical interpreter; nexi also calls the same interpreter directly | `xnch/agents/pipeline_graph.py:classify_intent`, `nexi/goal/driver.py:_run_goal_step` |
| Context assembly (LangGraph node) | shared (nexi impl) | `xnch/agents/pipeline_graph.py:52` → `nexi/pipeline/context_assembler.py:assemble_context` | Node delegates to nexi's context assembler; nexi also calls the same assembler | `xnch/agents/pipeline_graph.py:assemble_context`, `nexi/pipeline/run.py:load_context` |
| Option generation (LangGraph node) | shared (nexi impl) | `xnch/agents/pipeline_graph.py:90` → `nexi/pipeline/option_generator.py:generate_options` | Node delegates to nexi generator; nexi also calls it directly | `xnch/agents/pipeline_graph.py:generate_options`, `nexi/pipeline/run.py:generate_options` |
| Policy filter (LangGraph node) | shared (nexi impl) | `xnch/agents/pipeline_graph.py:113` → `nexi/pipeline/policy_filter.py:PolicyFilter.filter` | Node delegates to nexi PolicyFilter; nexi also calls it directly | `xnch/agents/pipeline_graph.py:filter_policy`, `nexi/pipeline/run.py:policy_filter.filter` |
| Scoring/evaluate (LangGraph node) | shared (nexi impl) | `xnch/agents/pipeline_graph.py:141` → `nexi/pipeline/evaluator.py:Evaluator.score` | Node delegates to nexi Evaluator; nexi also calls it directly | `xnch/agents/pipeline_graph.py:evaluate`, `nexi/pipeline/run.py:evaluator.score` |
| Select decision (LangGraph node) | shared (nexi impl) | `xnch/agents/pipeline_graph.py:178` → `nexi/pipeline/selector.py:select_decision` | Node delegates to nexi select_decision; nexi also calls it directly | `xnch/agents/pipeline_graph.py:select`, `nexi/pipeline/run.py:select_decision` |
| Plan compilation (LangGraph node) | shared (nexi impl) | `xnch/agents/pipeline_graph.py:234` → `nexi/pipeline/plan_compiler.py:compile_action_spec` | Node delegates to nexi compiler; nexi also calls it directly | `xnch/agents/pipeline_graph.py:compile_plan`, `nexi/pipeline/run.py:compile_action_spec` |
| Pipeline runtime (LangGraph invoke/resume) | xnch | `xnch/agents/pipeline_runtime.py:38` (`PipelineRuntime`) | Wraps `create_pipeline` with durable checkpointer and interrupt/resume for gateway/HITL flows; calls nexi modules at node boundaries | `xnch/agents/pipeline_runtime.py:invoke`, `xnch/agents/pipeline_runtime.py:resume` |
| HITL helpers (interrupt, resume) | xnch | `xnch/agents/hitl.py:13` (`normalize_resume`, `should_interrupt_execution`) | HITL gate logic is an xnch concern (trust tiers, approvals); consumed only by xnch decision graph/runtime | `xnch/agents/pipeline_graph.py:select`, `xnch/agents/pipeline_runtime.py:resume` |
| Decision graph state types | xnch | `xnch/agents/decision_state.py:1` (`DecisionState`, `Intent`, ...) | LangGraph state schema for the xnch/HITL decision graph | `xnch/agents/pipeline_graph.py:14` |
| 12-step pipeline pass | nexi | `nexi/pipeline/run.py:36` (`run_pipeline_pass`) | Canonical non-HITL pipeline; imported by nexi goal driver + workflow executor | `nexi/goal/driver.py:_run_goal_step`, `nexi/workflow/executor.py:_default_execute_step` |
| Goal driver (claim → run goal step) | nexi | `nexi/goal/driver.py:73` (`goal_driver_loop`) | Runs the nexi goal loop; claims goals from xnch, updates goal status via xnch API | `nexi/main.py` (lifespan entry) |
| Workflow executor (claim → run → dispatch) | nexi | `nexi/workflow/executor.py:147` (`workflow_executor_loop`) | Claims APPROVED workflow steps from xnch, runs pipeline, dispatches action spec to `nexi/execution/main.py` | `nexi/main.py` (lifespan entry) |
| Sandboxed action execution runner | nexi | `nexi/execution/main.py:54` (`app`) | Serves `/execution/execute` for running action specs; only nexi hosts this runner | `nexi/workflow/executor.py:_dispatch_execution` |
| Goal-step approval filing (HITL gate) | xnch | `xnch/jobs/goal_dispatch.py:67` (`run_due_dispatch`) | Cron claims due goal steps and files goal_step APPROVALs (HITL gate); runs no pipeline itself | `xnch/jobs/goal_dispatch.py:run_due_dispatch`, timer trigger |
| Scheduled workflow cron registration | xnch | `xnch/jobs/workflow_schedule.py:60` (`make_fire_fn`) | APScheduler registration of workflow runs; triggers xnch workflow runs that nexi later claims | `xnch/jobs/workflow_schedule.py:sync_all_workflow_jobs` |
| Consolidation (graph extraction + decay) | xnch | `xnch/jobs/consolidation.py:17` (`run_consolidation`) | Cron job tied to memory-service / consolidation timer; uses xnch memory stores | `xnch/jobs/consolidation.py:run_consolidation`, `consolidation.timer` |
| Proactivity engine | nexi | `nexi/proactivity/engine.py:46` (`ProactivityEngine`) | Generates proactivity suggestions from patterns, infra probes, and learning silence; nexi-only | `nexi/main.py` (lifespan entry) |
| Goal step planner (input + simulation) | nexi | `nexi/goal/planner.py:4` (`build_step_input`, `build_simulation`) | Pure helpers feeding nexi goal driver | `nexi/goal/driver.py:_run_goal_step` |

## Confirmed duplicates / overlaps

None confirmed. The two pipeline paths are complementary, not duplicated:

- `nexi/pipeline/run.py` is the canonical 12-step pipeline used by nexi goal/workflow execution; it imports and calls nexi pipeline modules directly.
- `xnch/agents/pipeline_graph.py` is a LangGraph decision graph whose nodes delegate to the same nexi pipeline modules, and whose runtime (`xnch/agents/pipeline_runtime.py`) adds durable checkpointer + interrupt/resume for gateway/HITL flows. `xnch/agents/pipeline_graph.py` is not a copy of `nexi/pipeline/run.py`; it wraps the same canonical modules behind LangGraph nodes.

Because neither is a duplicate, no code moves are proposed here. If both paths are ever run for the same decision context simultaneously, add a tracking issue before any merge.

## Proposed follow-ups

None in Phase 1 (no confirmed duplicates to move).
