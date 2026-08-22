# Governance HITL Pipeline (LangGraph)

The LangGraph decision pipeline runs **inside xnch** when the pipeline runtime is
ready. It is backed by an `AsyncPostgresSaver` checkpointer
(`xnch/agents/pipeline_runtime.py`) and the compiled graph in
`xnch/agents/pipeline_graph.py`.

> Enabled surface: `XNCH_LANGGRAPH_PIPELINE=true` (the runtime still starts even
> when false, but the flag documents the intended HITL path). All three endpoints
> return `503 Pipeline runtime not available` if `PipelineRuntime.ready` is false
> (e.g. Postgres checkpointer failed at startup).

Graph nodes (`create_pipeline`): `classify_intent → assemble_context →
generate_options → filter_policy →(evaluate|end)→ evaluate → select →
(compile_plan|end)→ compile_plan → dispatch → END`.

On an `EXECUTION` intent, the `select` node calls `interrupt()` with
`{action: "approve_execution", selected, intent, decisions: ["approve","reject"]}`
when `should_interrupt_execution(...)` matches (mode `always` by default —
see [config.md](config.md) `XNCH_HITL_EXECUTION_MODE` / `XNCH_HITL_RISK_THRESHOLD`).

---

## Base URL

```
http://192.168.1.10:8001
```

---

## 1. POST `/governance/pipeline/invoke`

Start a new (or resume-into-existing) pipeline run for a thread.

### Request

```json
{
  "session_id": "6f3c…",
  "raw_input": "deploy v1.2.0 to production",
  "trace_id": "optional-uuid",
  "thread_id": "optional-uuid"
}
```

`session_id` and `raw_input` are required; `trace_id` / `thread_id` default to a
fresh uuid4 if omitted.

### Response — interrupted (HITL waiting on approval)

```json
{
  "status": "interrupted",
  "thread_id": "b7e1…",
  "interrupts": [
    {
      "action": "approve_execution",
      "selected": {
        "option_id": "…",
        "action_spec": { "type": "deploy", "entity_class": "service", "payload": {} }
      },
      "intent": {"intent_class": "EXECUTION", "…": "…"},
      "decisions": ["approve", "reject"]
    }
  ],
  "state": { "raw_input": "…", "session_id": "…", "events": [], "…": "…" }
}
```

### Response — completed (no interrupt, or non-EXECUTION intent)

```json
{
  "status": "completed",
  "thread_id": "b7e1…",
  "result": {
    "raw_input": "…",
    "session_id": "…",
    "events": [
      {"type": "intent_classified", "intent_class": "QUERY"},
      {"type": "manifest_pinned", "manifest_id": "…"},
      {"type": "options_generated", "count": 3, "path": "…"},
      {"type": "options_evaluated", "count": 3},
      {"type": "option_selected", "option_id": "…"},
      {"type": "plan_compiled"},
      {"type": "dispatched", "plan": {…}}
    ]
  }
}
```

### Errors

| Code | Condition |
|------|-----------|
| 503 | pipeline runtime not ready |
| 500 | pipeline invoke raised (details in `detail`) |

---

## 2. POST `/governance/pipeline/resume`

Resume an interrupted thread with a human decision.

### Request

```json
{
  "thread_id": "b7e1…",
  "decision": "approve"
}
```

`decision` accepts `"approve"` / `"reject"` (case-insensitive, plus
`approved`/`true`/`yes`/`1` aliases). Alternatively pass `"approved": true|false`.
At least one of `decision` / `approved` must be provided.

### Response — rejected

```json
{
  "status": "completed",
  "thread_id": "b7e1…",
  "approved": false,
  "decision": "reject",
  "result": {
    "selected": null,
    "events": [ {"type": "execution_rejected"} ]
  }
}
```

### Response — approved (pipeline continues)

```json
{
  "status": "completed",
  "thread_id": "b7e1…",
  "approved": true,
  "decision": "approve",
  "result": {
    "selected": { "option_id": "…", "action_spec": {…} },
    "events": [
      {"type": "option_selected", "option_id": "…"},
      {"type": "plan_compiled"},
      {"type": "dispatched", "plan": {…}}
    ]
  }
}
```

If the resumed run hits *another* interrupt (multi-gate pipeline), the response
is `status: "interrupted"` with the new `interrupts` array — call `/resume`
again with a new decision.

### Errors

| Code | Condition |
|------|-----------|
| 503 | pipeline runtime not ready |
| 404 | no pending interrupt for `thread_id` (`LookupError`) |
| 422 | neither `decision` nor `approved` provided (`ValueError`) |
| 500 | unexpected resume failure |

---

## 3. GET `/governance/pipeline/{thread_id}`

Inspect thread state, next nodes, and pending interrupts.

### Request

```
GET /governance/pipeline/b7e1…
```

### Response

```json
{
  "thread_id": "b7e1…",
  "next": ["select"],
  "interrupts": [
    {
      "action": "approve_execution",
      "selected": { "option_id": "…" },
      "intent": {"intent_class": "EXECUTION"},
      "decisions": ["approve", "reject"]
    }
  ],
  "values": { "raw_input": "…", "session_id": "…", "events": [ … ] }
}
```

- `next` — list of nodes that will run next (from `snapshot.next`).
- `interrupts` — pending `interrupt()` values; empty when the thread is
  waiting/completed.
- `values` — current graph state dict.

### Errors

| Code | Condition |
|------|-----------|
| 503 | pipeline runtime not ready |

---

## End-to-end example (curl)

```bash
BASE=http://192.168.1.10:8001

# 1) Invoke an EXECUTION intent → expect status "interrupted"
curl -sS -X POST $BASE/governance/pipeline/invoke \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"6f3c9a2e","raw_input":"deploy v1.2.0 to prod"}' \
  | tee /tmp/invoke.json

THREAD=$(python3 -c "import json;print(json.load(open('/tmp/invoke.json'))['thread_id'])")

# 2) Inspect the pending interrupt
curl -sS $BASE/governance/pipeline/$THREAD | python3 -m json.tool

# 3) Approve → expect status "completed" with plan dispatched
curl -sS -X POST $BASE/governance/pipeline/resume \
  -H 'Content-Type: application/json' \
  -d "{\"thread_id\":\"$THREAD\",\"decision\":\"approve\"}" | python3 -m json.tool
```

---

## Implementation notes

- `PipelineRuntime.invoke()` starts graph with
  `{"raw_input", "session_id", "trace_id", "events": []}` and
  `configurable.thread_id`.
- `PipelineRuntime.resume()` resumes with
  `Command(resume=...)` — `{"decision": "approve"|"reject"}` when `decision` was
  given, else the raw bool from `approved`.
- `normalize_resume()` (`xnch/agents/hitl.py`) maps resume payloads to bool:
  `True/"approve"/{"decision":"approve"} → True`, mirror for reject.
- The HITL gate applies only to `intent_class == "EXECUTION"`. Interrupt
  payload shape is defined in `select` node of `xnch/agents/pipeline_graph.py`.
