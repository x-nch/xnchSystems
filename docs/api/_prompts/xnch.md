Document the **xnch** control-plane APIs separately.

OUTPUT FOLDER (write ONLY here — do not put files elsewhere):
  docs/api/xnch/

Scope for THIS session = the `xnch/` package / submodule only:
- FastAPI app (`xnch/main.py`) and all routers under `xnch/routes/`
- Every HTTP route: method, path, request/response models, auth requirements
- Memory, policy, governance (including /governance/pipeline/invoke|resume), nexi gateway, session, system, auth
- Key stores/adapters only as they affect API behavior
- Config: XNCH_* settings / env
- LangGraph HITL pipeline surface if exposed via xnch routes

Deliverables (markdown):
1. docs/api/xnch/README.md — index
2. docs/api/xnch/overview.md — control-plane role vs nexi
3. docs/api/xnch/endpoints.md — complete HTTP API reference grouped by router
4. docs/api/xnch/models.md — important request/response models
5. docs/api/xnch/governance-hitl.md — invoke/resume/get thread APIs with examples
6. docs/api/xnch/config.md — settings / env vars

Rules:
- Read real FastAPI routers and Pydantic models; do not invent endpoints
- Prefer endpoint tables
- Example base URL: http://192.168.1.10:8001 (gate7)
- No commits, no push, no deploy
- Mark TODOs instead of guessing
