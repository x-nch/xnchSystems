# xnch REST API (:8001)

Sources: route decorators in `xnch/routes/*.py`, `xnch/main.py`. Request/response
shapes are the Pydantic models beside each handler — treat this page as the map,
the code as the schema. Auth column: `open` = no bearer required;
`actor` = actor bearer token; `gateway` = gateway access
([Hybrid-B](auth-model.md#gateway-hybrid-b)) or service key.

## System

| Method & path | Auth | Purpose |
|---|---|---|
| GET `/health` | open | liveness + Redis + bridge summary |
| GET `/system/state` | actor | `system_state_version` / `policy_version` (session/init must match or 409) |
| GET `/system/llm-status` | actor | probes vLLM Ornith (`XNCH_LLM_STATUS_URL`) |

## Session & decision loop

| Method & path | Auth | Purpose |
|---|---|---|
| POST `/session/init` | actor | dedup/rate-limit, forward to nexi `/session/start` |
| POST `/session/{id}/clarify` | actor | clarification sub-session |
| GET/POST `/policy/check` | actor | policy engine evaluation (first-match-wins YAML rules) |
| POST `/verdict` | actor | authoritative decision eval → ALLOW(+RS256 token)/BLOCK; ledger write |
| POST `/execution/execute` | actor | dispatch step (stub runner) |
| POST `/execution/outcome` | actor | SUCCESS/PARTIAL/FAILURE; completes episodes; nexi callback |

## Memory

| Method & path | Auth | Purpose |
|---|---|---|
| POST `/memory/read` | actor | ContextManifest for pipeline (episodes, patterns, policy refs) |
| POST `/memory/write` | actor | guard-checked writes (`validate_memory_write`) |
| GET `/memory/graph/stats` | actor | tier counts, cross-tier edges |
| GET `/memory/graph/entities` · `/relations` · `/subgraph` | actor | paginated graph views (`tier=&search=&limit=&offset=`) |
| GET `/memory/graph/stream` | actor | SSE live graph updates |

> `tier_graph.py` additionally designs `/memory/graph/tiers` + `/all`
> (unified cross-tier view) — docstring only, **not routed yet**.

## Nexi gateway & chat → see [api-gateway-chat](api-gateway-chat.md)

## Governance & admin

| Method & path | Auth | Purpose |
|---|---|---|
| GET `/governance/weights` | actor | current scoring weights |
| POST `/governance/weights/propose` · `/approve` | actor | weight change proposals (HITL); approve runs a fitness regression gate vs the active config — regressions rejected unless `force=true` |
| POST `/governance/actors` | actor | register actors |
| GET `/governance/policy-candidates` | actor | learning-loop candidates (review only — no programmatic promotion path; live rules load from `policies/*.yaml` via the PolicyLoader, so promotion = human review then a manual YAML edit) |
| POST `/governance/pipeline/invoke` · `/resume`; GET `/governance/pipeline/{thread_id}` | actor | optional LangGraph pipeline w/ interrupts (`XNCH_LANGGRAPH_PIPELINE`) |
| POST `/admin/consolidate` | actor | consolidation pass (timer calls this) |
| POST `/admin/reseed-identity` | actor | cold-start identity facts |

## Goals

| Method & path | Auth | Purpose |
|---|---|---|
| POST `/goals` · GET `/goals` · GET `/goals/{id}` | actor | create/list/read goals |
| POST `/goals/claim` | actor | atomic lease claim (`claim_next_goal`) |
| POST `/goals/{id}/update` · `/step-outcome` · `/cancel` | actor | progress tracking |

Goal driver loop on nexi side is gated by `NEXI_GOAL_DRIVER_ENABLED` (default off).

## Agent dispatch (`/agents/*`)

All methods — reads included — require the Hybrid-B gateway token (or service key). Run `result_text`/`error` are secret-redacted at the storage boundary (session-ingest redactor) before any endpoint can serve them.

| Method & path | Auth | Purpose |
|---|---|---|
| POST `/agents/dispatch` | gateway | queue a run for the Mac runner. **403 unless `XNCH_AGENTS_DIRECT_DISPATCH_ENABLED=1`** — approval-bypass path, deny-by-default |
| POST `/agents/dispatch/next` | gateway | runner claims oldest QUEUED (lease-based); writes CLAIMED step_event when linked to a goal approval |
| POST `/agents/runs/{id}/outcome` | gateway | terminal DONE/FAILED + exit code + redacted result_text/error; back-pressures goal step-outcome |
| GET `/agents/runs/{id}` · GET `/agents/runs?status=` | gateway | run detail / list |

Goal-driven auto-dispatch: cron files goal_step approvals from the active goal's plan; every approval carries `risk_class` (`low` only on explicit allowlist match, else `elevated`). Deciding an `elevated` approval requires header `X-Actor-Role: admin`.

## Workflows & approvals → table in [workflows architecture](../architecture/workflows-hitl.md#api-surface)

## Voice (`/nexi/voice/*`)

POST `/transcribe` (STT), `/speak`, `/speak/upload` (TTS via piper),
`/chat` (voice-in → chat → voice-out). Limits:
`XNCH_VOICE_MAX_AUDIO_DURATION_S`=60, `XNCH_VOICE_MAX_AUDIO_BYTES`=10 MiB,
`XNCH_VOICE_MAX_TTS_CHARS`=2000.

## MCP HTTP → [mcp-http-api](mcp-http-api.md)

GET `/mcp/tools` · `/tools/openai` · `/servers`; POST `/mcp/call` · `/call/batch`.

## Auth

GET `/auth/public-key` — RSA public key for execution-token verification.
