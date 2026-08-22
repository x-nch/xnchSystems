# xnch Control-Plane API Reference

The **xnch** service (`xnch` git submodule → `github.com/x-nch/xnch`) is the
governance, memory, and authorization control plane. This reference documents
its HTTP API as served by the FastAPI app in `xnch/main.py`.

- **Base URL (gate7):** `http://192.168.1.10:8001`
- **Interactive docs:** `http://192.168.1.10:8001/docs` (OpenAPI)
- **Version:** `0.1.0`
- **Auth model:** actor tokens verified against `XNCH_AUTH_SECRET` (HS256), plus
  RS256 execution tokens issued by xnch and consumed by the executor.

## Documents

| Doc | Contents |
|-----|----------|
| [overview.md](overview.md) | Control-plane role vs the nexi execution engine, pipeline flow, auth model |
| [endpoints.md](endpoints.md) | Complete HTTP API reference grouped by router (method · path · models · auth) |
| [models.md](models.md) | Important request / response models |
| [governance-hitl.md](governance-hitl.md) | LangGraph HITL pipeline — `/governance/pipeline/invoke`, `/resume`, `/pipeline/{thread_id}` with examples |
| [config.md](config.md) | `XNCH_*` settings / environment variables |

## Router index

| Prefix | Router | File |
|--------|--------|------|
| `/health`, `/system/state` | app-level | `xnch/main.py` |
| `/session` | session_router | `xnch/routes/session.py` |
| `/memory` | memory_router | `xnch/routes/memory.py` |
| `/policy` | policy_router | `xnch/routes/policy.py` |
| `/verdict` | verdict_router | `xnch/routes/verdict.py` |
| `/execution` | execution_router | `xnch/routes/execution.py` |
| `/governance` | governance_router | `xnch/routes/governance.py` |
| `/auth` | auth_router | `xnch/routes/auth.py` |
| `/nexi` | nexi_gateway_router | `xnch/routes/nexi_gateway.py` |
| `/nexi/voice` | voice_router | `xnch/routes/voice.py` |
| `/v1/chat/completions` | chat_router | `xnch/routes/chat.py` |
| `/admin` | admin_router | `xnch/routes/admin.py` |
| `/mcp` | mcp_router | `xnch_mcp/http_router.py` (external package) |

## Endpoint count

40 HTTP routes total:
- 2 app-level (`/health`, `/system/state`)
- 8 memory (incl. 4 graph + 1 SSE)
- 2 policy (`GET` + `POST` on the same handler)
- 6 governance (2 weights + actors + candidates + 3 pipeline HITL)
- 6 nexi gateway
- 4 voice
- 3 admin + auth + chat + session + verdict + 2 execution + 5 mcp

## Quick start examples

```bash
BASE=http://192.168.1.10:8001

# health
curl $BASE/health

# public key for RS256 execution-token verification
curl $BASE/auth/public-key

# memory read (context manifest) — POST JSON, actor claims in body
curl -X POST $BASE/memory/read \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"...","actor_id":"operator","actor_role":"OPERATOR","query":{"intent_class":"EXECUTION"}}'

# LangGraph HITL pipeline
curl -X POST $BASE/governance/pipeline/invoke \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"...","raw_input":"deploy v1.2 to prod"}'
```

## Scope & caveats

- This reference is generated from source at commit
  `f3297491473486847029a725b0b432c4430d0cc8` (xnch submodule HEAD).
- Routers mounted from the **external `xnch_mcp` package** (`/mcp/*`) are
  included in [endpoints.md](endpoints.md) but are documented as a dependency.
- Nothing here has been committed; see [config.md](config.md) for gate7 env.
