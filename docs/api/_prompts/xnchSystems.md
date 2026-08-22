Document the **xnchSystems** (meta/repo-level) APIs and integration surfaces.

OUTPUT FOLDER (write ONLY here — do not put files elsewhere):
  docs/api/xnchSystems/

Scope for THIS session = the monorepo glue, NOT the full xnch or nexi package internals:
- Root entrypoints, scripts, CLI (`cli/`), e2e tests (`tests/`), infra HTTP surfaces that span both nodes
- How Mac/CLI talks to gate7 (xnch :8001) and Node B (nexi :8000)
- Cross-cutting routes exposed via xnch that proxy/gateway to nexi (e.g. /nexi/chat)
- Governance HITL pipeline routes if they live at the control-plane boundary
- Env vars that configure the whole system (XNCH_*, NEXI_*, LiteLLM)

Deliverables (markdown):
1. docs/api/xnchSystems/README.md — index + how to use these docs
2. docs/api/xnchSystems/overview.md — architecture of the multi-repo API surface
3. docs/api/xnchSystems/cli.md — `python -m cli` commands with examples
4. docs/api/xnchSystems/endpoints.md — table of top-level HTTP endpoints reachable from Mac (base http://192.168.1.10:8001) with method, path, purpose, request/response shape summary
5. docs/api/xnchSystems/auth.md — auth headers/tokens if any

Rules:
- Prefer reading real FastAPI route files / CLI code over inventing APIs
- Use accurate path/method/schema names from code
- No commits, no push, no deploy
- Keep docs factual and concise
- If something is unclear, mark TODO rather than guessing
