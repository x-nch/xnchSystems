# Deep-agents pattern borrow (no package)

**Decision:** Do **not** re-add the `deepagents` package (previously adopted then dropped in `cae0295`). Borrow patterns as ~100-line implementations inside `xnch`/`nexi`, keeping deps at `langgraph` + `langgraph-checkpoint-postgres`.

## Patterns to borrow

| Pattern | Source idea | xnchSystems placement |
|---|---|---|
| Checkpointed HITL | `interrupt()` + required checkpointer + `Command(resume=...)` | **Done** — `pipeline_graph.select` + `pipeline_runtime` + `/governance/pipeline/*` |
| Typed resume | `approve \| reject` | **Done** — `hitl.ResumeDecision` + `/governance/pipeline/resume` `decision` field (bool `approved` still accepted) |
| `when`-predicates | Interrupt only when args match a condition | **Done (v1)** — `hitl.should_interrupt_execution` modes: `always` / `risk_threshold` / `never` via `XNCH_HITL_EXECUTION_MODE` |
| Todo-state planning | `TodoListMiddleware` state shape | Optional planning node state in decision graph; not a LangChain middleware stack |
| CompositeBackend drafts | Draft FS vs publish FS | Future codegen: virtual-FS drafts → HITL-gated apply into a **git worktree** (worktrees remain the apply surface) |
| LangGraph as default path | Feature flag | `XNCH_LANGGRAPH_PIPELINE` — when true, startup logs HITL-ready; invoke stays on `/governance/pipeline/*` (nexi imperative path unchanged) |

## Interview one-liner

> A checkpointed hard interrupt at the loop-1 actuation boundary — default-deny, resumable on explicit approval — with loop-4 harness changes themselves gated through human governance review.

## Codegen composition (specified, not built)

1. Agent drafts into StateBackend / CompositeBackend draft route  
2. Human approves via HITL resume  
3. Apply materializes into a git worktree where compilers/tests/opencode run  
4. Crash-safe cleanup of the worktree  

`codegen_loop.py` remains absent by design until that wave.
