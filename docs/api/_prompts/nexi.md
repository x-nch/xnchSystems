Document the **nexi** execution-engine APIs separately.

OUTPUT FOLDER (write ONLY here — do not put files elsewhere):
  docs/api/nexi/

Scope for THIS session = the `nexi/` package / submodule only:
- FastAPI app entry (`nexi/main.py`) — list every route with method, path, request body, response
- Pipeline modules and how they map to HTTP if exposed
- Models that appear in request/response (Intent, SessionContext, ContextManifest, PlanOption, etc.) — summarize fields
- Health, decision/session endpoints, any eval CLI (`python -m nexi.eval.cli`)
- Config: NEXI_* env / settings
- How nexi calls xnch (XnchClient base URL, key paths)

Deliverables (markdown):
1. docs/api/nexi/README.md — index
2. docs/api/nexi/overview.md — what nexi is / responsibility boundary vs xnch
3. docs/api/nexi/endpoints.md — complete HTTP API reference from code
4. docs/api/nexi/models.md — key Pydantic models used on the wire
5. docs/api/nexi/pipeline.md — decision pipeline stages (intent → … → dispatch) as an API-oriented flow
6. docs/api/nexi/config.md — settings / env vars

Rules:
- Read real route definitions and models; do not invent endpoints
- Prefer tables for endpoints
- Include example curl where helpful (nexi typically :8000 on Node B)
- No commits, no push, no deploy
- Mark TODOs instead of guessing
