# Nexi API docs

API reference for the **nexi** execution/decision engine (git submodule →
`github.com/x-nch/nexi`). Nexi is the FastAPI decision engine that turns a
resolved session + raw user input into a scored, policy-vetted decision, then
dispatches execution. It runs on **Node B** and typically listens on **:8000**.

These docs cover the `nexi/` package only. For the xnch control plane (which
nexi calls out to) see `docs/api/xnch/` / `docs/api/xnchSystems/`.

## Documents

| Doc | Purpose |
|-----|---------|
| [overview.md](overview.md) | What nexi is, responsibility boundary vs xnch, runtime placement |
| [endpoints.md](endpoints.md) | Complete HTTP API reference (`/session/start`, `/callback/outcome`, `/health`, `/nexi/capabilities`, `/nexi/refresh`) with curl |
| [models.md](models.md) | Key Pydantic models used on the wire (Intent, SessionContext, ContextManifest, PlanOption, …) |
| [pipeline.md](pipeline.md) | Decision pipeline as an API-oriented flow (Step 3 intent → Step 11 dispatch → Step 14 callback) |
| [config.md](config.md) | `NEXI_*` env vars / `nexi/config.py` settings |

## Quick orientation

- **App entry:** `nexi/main.py` — FastAPI app `Nexi v0.1.0`, lifespan instantiates
  `XnchClient`, `ModelAdapter`, `PolicyFilter`, `IntentInterpreter`.
- **HTTP surface:** five routes — `POST /session/start`, `POST /callback/outcome`,
  `GET /health`, `GET /nexi/capabilities`, `POST /nexi/refresh`.
- **Primary caller:** xnch calls `POST /session/start` after actor resolution;
  nexi calls xnch's `/memory/read`, `/policy/check`, `/verdict`, `/memory/write`,
  `/governance/weights`, and `/execution/outcome`.
- **Model routing:** option generation and intent classification go through
  LiteLLM proxy → vLLM → llama.cpp → rule-based fallback.
- **Eval CLI:** `python -m nexi.eval.cli --fixture` — deterministic offline
  smoke suite (see [overview.md](overview.md#eval-cli)).

## Source of truth

- `nexi/main.py`, `nexi/config.py`, `nexi/adapters/xnch_client.py`, `nexi/adapters/model_adapter.py`
- `nexi/models/*.py`
- `nexi/pipeline/*.py`
- `nexi/eval/{cli,harness,grader,cases,store}.py`
- `nexi/proactivity/engine.py`, `nexi/character/*.py`, `nexi/utils/*.py`

When a behavior is ambiguous, docs mark it `TODO` instead of guessing.
