# Handoff: beeAI & AgentStack integration into Xnch

Copy everything below the line into a new agent session (Cursor / OpenCode).

---

## Status

**COMPLETE and verified.** beeAI orchestration path is wired into xnch as a feature-flagged FastAPI router. Demo mode works end-to-end via `TestClient` against the real `xnch.main` app. 293 unit tests pass (incl. 6 new beeai tests).

Full session log: `beeAi-poc.md` (root).

## What it is

Side-by-side, opt-in alternative to the LangGraph/nexi decision pipeline. A beeAI `RequirementAgent` runs over the same in-process MCP tool registry that powers `/mcp/call`. Philosophy: deterministic policy gates enforced by the framework, not LLM suggestions.

- Gated by `XNCH_BEEAI_ENABLED` (default off → `/beeai/*` returns 404 "beeai engine disabled").
- Demo/degraded mode via `XNCH_BEEAI_DEMO_MODE` + `StaticChatModel` stub (no backend needed).
- Production path: beeAI OpenAI-compatible ChatModel → LiteLLM proxy (`settings.litellm_proxy_url`) → vLLM (Ornith).

## Files (all inside `xnch` submodule)

```
xnch/agents/beeai/__init__.py   # re-exports
xnch/agents/beeai/backend.py    # StaticChatModel, build_chat_model (OpenAI→LiteLLM)
xnch/agents/beeai/tools.py      # beeai @tool wrappers over xnch_mcp.registry.invoke_tool
xnch/agents/beeai/policies.py   # PolicyGateRequirement, approval_requirement, build_requirements
xnch/agents/beeai/agent.py      # build_orchestrator (RequirementAgent)
xnch/agents/beeai/swarm.py      # build_swarm: context_bee + planner_bee (AgentWorkflow)
xnch/agents/beeai/runtime.py    # run_agent / run_swarm / _extract_text / audit events
xnch/agents/beeai/route.py      # beeai_router: GET /beeai/health, POST /beeai/chat, POST /beeai/swarm
xnch/tests/test_beeai.py        # 6 passing tests
```

Also touched: `xnch/config.py` (beeai settings block after `litellm_proxy_url`), `xnch/main.py` (conditional router mount ~line 179). `pyproject.toml`/`uv.lock` at root already have `beeai-framework>=0.1.82,<0.2` (pre-existing).

## Verified endpoints (demo mode)

```bash
curl -s localhost:8001/beeai/health   # {"status":"ok","engine":"beeai","enabled":true,"demo_mode":true,"model":"ornith"}
curl -s -X POST localhost:8001/beeai/chat  -H 'X-Actor-Role: operator' -H 'Content-Type: application/json' -d '{"message":"hi"}'
curl -s -X POST localhost:8001/beeai/swarm -H 'X-Actor-Role: operator' -H 'X-BeeAI-Approval: allow' -H 'Content-Type: application/json' -d '{"message":"hi"}'
```

Response shape: `{"engine":"beeai","text":"beeAI demo response (no LLM configured)","tool_count":5,"duration_ms":12}`.

## Headers / gating

- Actor: `X-Actor-Role` (default `"external"` in beeai route; `"operator"` in `xnch_mcp/http_router.py`), `X-Trace-Id` (uuid4 fallback), `X-Session-Id`.
- Approval: `X-BeeAI-Approval: allow` → `approve=True` for mutating tools.
- Policy stack: `PolicyGateRequirement(default_policy_checker())` + `AskPermissionRequirement`. `MUTATING_TOOLS = {"xnch_memory_store_note", "xnch_exec_run"}`.
- Audit: runtime emits `AGENT_RUN`/`SWARM_RUN` via `event_log`; route emits `BEEAI_CHAT`/`BEEAI_SWARM` via `xnch.memory.audit_store.emit_event(trace_id, component, event_type, payload)` (positional payload — NOT `data=`). Note `xnch/utils/audit.py` does NOT exist.

## beeai-framework 0.1.82 gotchas (verified via inspect — do not "fix" these)

1. `RequirementAgent`/`ToolCallingAgent` constructors have **no** `execution`/`max_iterations` — pass `max_iterations` to `.run()`.
2. `AgentWorkflow.run` takes `Sequence[AgentWorkflowInput | Message]` — a bare `[{"prompt": ...}]` dict fails with `'dict' object has no attribute 'text'`. Use `[AgentWorkflowInput(prompt=message)]`.
3. `ChatModelOutput(output=[AssistantMessage(...)], finish_reason=...)` requires `output` to be a **list**, not a single message.
4. Custom ChatModel must call `super().__init__()` or `_middlewares` is missing (`AttributeError`).
5. `AskPermissionRequirement(include=[...])` validates that every included tool exists in the agent's toolset (`_assert_all_rules_found`). Filter `include` to tools present (done in `policies.py`) — the swarm's `context_bee` excludes `xnch_exec_run`.
6. `StaticChatModel` keeps default `tool_choice_support` (incl. `"required"`). Removing `"required"` made text extraction return empty — reverted. The framework logs a cosmetic `ERROR` line (`ChatModelToolCallError` is caught in `_runner._run_llm` and the text is reused as the final answer). Harmless in demo mode.
7. Result extraction: swarm → `response.result.final_answer` (str); agent → `response.last_message.text` / `response.state.answer` (AssistantMessage). See `_extract_text` in `runtime.py`.

## Known non-issues (resolved)

- "App only has 7 routes / /beeai missing" was NOT a bug: this FastAPI version uses lazy `_IncludedRouter` entries so `app.routes` doesn't flatten `include_router`. Router is mounted correctly; verified via `TestClient`.
- `request.app.state.event_log` may not exist when lifespan hasn't run → route uses `getattr(..., None)`.

## Pre-existing test failures (NOT from this work)

- `tests/test_voice_io.py` — missing `sounddevice`.
- `tests/test_nexi_chat_e2e.py` — needs running services.
- `xnch_mcp/tests/test_exec_handlers.py::test_handler_run` — hardcoded path `/System/Volumes/Data/home/x-nch/xnchSystems` from another machine.

## Env facts

- Root `.venv` is uv-managed, Python 3.13.9. `pip list` shows 0 packages — use `uv pip list --python .venv/bin/python`.
- `timeout` command unavailable on macOS zsh.
- Smoke-test pattern (works without services):
  ```bash
  .venv/bin/python -m pytest xnch/tests nexi/tests -q
  ```

## If you extend this

- Real model path: `build_chat_model()` → OpenAIChatModel via `load_model("openai")` pointed at LiteLLM proxy.
- `build_tools` currently returns 5 hardcoded wrappers filtered by `list_tools_for_actor(role)`; registry is source of truth for gating.
- Swarm uses `RequirementAgent` bees (agent.py builds only RequirementAgent — `__init__.py` docstring already corrected).
