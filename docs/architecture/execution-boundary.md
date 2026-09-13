# Execution Boundary: xnch vs nexi

## The rule
nexi owns DECIDING (the 12-step pipeline that turns a user turn into an action
spec). xnch owns ORCHESTRATING (scheduling crons, dispatching to runners,
HITL approvals, gateway/API surface).

## Architecture (post-M5)

The following subsystems were **retired in M5** — replaced by Hermes, Gas Town,
and the promoted LangGraph supervisor graph:

| Retired subsystem | Owner (was) | Replacement |
|---|---|---|
| `nexi/goal/` (driver, planner) | nexi | Hermes native automations |
| `nexi/proactivity/` (engine) | nexi | `xnch_mcp/handlers/memory.py::_memory_surface` (pgvector-backed, flag-gated) |
| `nexi/workflow/` (executor) | nexi | Gas Town workstreams + LangGraph supervisor |
| `xnch/jobs/goal_dispatch.py` | xnch | Retired (goal tracking removed) |
| `xnch/jobs/workflow_schedule.py` | xnch | Retired (workflow execution removed) |
| `xnch/memory/workflow_store.py` | xnch | `InMemoryApprovalStore` (for HITL approvals only) |
| `xnch/memory/agent_run_store.py` | xnch | Retired (Gas Town git-backed state) |
| `clients/agent-runner/` | Mac | Gas Town host (`clients/gastown/`) |

## Verified boundaries (surviving)

| Subsystem | Owner | Key file:line | Why it belongs there | Confirmed callers |
|---|---|---|---|---|
| Intent interpretation (LangGraph node) | shared (nexi impl) | `xnch/agents/pipeline_graph.py:35` → `nexi/pipeline/intent_interpreter.py:IntentInterpreter.interpret` | Node is a LangGraph wrapper around nexi's canonical interpreter; nexi also calls the same interpreter directly | `xnch/agents/pipeline_graph.py:classify_intent` |
| Context assembly (LangGraph node) | shared (nexi impl) | `xnch/agents/pipeline_graph.py:52` → `nexi/pipeline/context_assembler.py:assemble_context` | Node delegates to nexi's context assembler; nexi also calls it directly | `xnch/agents/pipeline_graph.py:assemble_context` |
| Option generation (LangGraph node) | shared (nexi impl) | `xnch/agents/pipeline_graph.py:90` → `nexi/pipeline/option_generator.py:generate_options` | Node delegates to nexi generator; nexi also calls it directly | `xnch/agents/pipeline_graph.py:generate_options` |
| Policy filter (LangGraph node) | shared (nexi impl) | `xnch/agents/pipeline_graph.py:113` → `nexi/pipeline/policy_filter.py:PolicyFilter.filter` | Node delegates to nexi PolicyFilter; nexi also calls it directly | `xnch/agents/pipeline_graph.py:filter_policy` |
| Scoring/evaluate (LangGraph node) | shared (nexi impl) | `xnch/agents/pipeline_graph.py:141` → `nexi/pipeline/evaluator.py:Evaluator.score` | Node delegates to nexi Evaluator; nexi also calls it directly | `xnch/agents/pipeline_graph.py:evaluate` |
| Select decision (LangGraph node) | shared (nexi impl) | `xnch/agents/pipeline_graph.py:178` → `nexi/pipeline/selector.py:select_decision` | Node delegates to nexi select_decision; nexi also calls it directly | `xnch/agents/pipeline_graph.py:select` |
| Plan compilation (LangGraph node) | shared (nexi impl) | `xnch/agents/pipeline_graph.py:234` → `nexi/pipeline/plan_compiler.py:compile_action_spec` | Node delegates to nexi compiler; nexi also calls it directly | `xnch/agents/pipeline_graph.py:compile_plan` |
| Pipeline runtime (LangGraph invoke/resume) | xnch | `xnch/agents/pipeline_runtime.py:38` (`PipelineRuntime`) | Wraps `create_pipeline` with durable checkpointer and interrupt/resume for gateway/HITL flows; calls nexi modules at node boundaries | `xnch/agents/pipeline_runtime.py:invoke`, `xnch/agents/pipeline_runtime.py:resume` |
| HITL helpers (interrupt, resume) | xnch | `xnch/agents/hitl.py:13` (`normalize_resume`, `should_interrupt_execution`) | HITL gate logic is an xnch concern (trust tiers, approvals); consumed only by xnch decision graph/runtime | `xnch/agents/pipeline_graph.py:select`, `xnch/agents/pipeline_runtime.py:resume` |
| Decision graph state types | xnch | `xnch/agents/decision_state.py:1` (`DecisionState`, `Intent`, ...) | LangGraph state schema for the xnch/HITL decision graph | `xnch/agents/pipeline_graph.py:14` |
| 12-step pipeline pass | nexi | `nexi/pipeline/run.py:36` (`run_pipeline_pass`) | Canonical non-HITL pipeline; called by LangGraph nodes | `xnch/agents/pipeline_graph.py` |
| Supervisor graph (spawn decisions) | xnch | `xnch/agents/supervisor_graph.py:39` (`decide`, `gate`) | LangGraph graph with HITL `interrupt()` gate; decides when to spawn workstreams | `xnch/agents/supervisor_graph.py:build_supervisor` |
| Sandboxed action execution runner | nexi | `nexi/execution/main.py:54` (`app`) | Serves `/execution/execute` for running action specs; only nexi hosts this runner | `xnch_mcp/exec/` |
| Consolidation (graph extraction + decay) | xnch | `xnch/jobs/consolidation.py:17` (`run_consolidation`) | Cron job tied to memory-service / consolidation timer; uses xnch memory stores | `xnch/jobs/consolidation.py:run_consolidation`, `consolidation.timer` |
| Proactivity surface (flag-gated) | xnch | `xnch_mcp/handlers/memory.py::_memory_surface` | Reads pgvector episodes (workstream/automation) when `proactivity_surface_enabled=True` | `xnch_mcp/handlers/memory.py` |
| Approval queue (HITL REST) | xnch | `xnch/routes/workflows.py` (`approvals_router`) | In-memory approval store backed by gateway token guard; serves web UI | `xnch/routes/workflows.py` |

## Confirmed duplicates / overlaps

None confirmed. The two pipeline paths are complementary, not duplicated:

- `nexi/pipeline/run.py` is the canonical 12-step pipeline called by LangGraph nodes.
- `xnch/agents/pipeline_graph.py` is a LangGraph decision graph whose nodes delegate to the same nexi pipeline modules, and whose runtime (`xnch/agents/pipeline_runtime.py`) adds durable checkpointer + interrupt/resume for gateway/HITL flows.

Because neither is a duplicate, no code moves are proposed here. If both paths are ever run for the same decision context simultaneously, add a tracking issue before any merge.

## Proposed follow-ups

None in Phase 1 (no confirmed duplicates to move).