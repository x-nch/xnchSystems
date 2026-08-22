# Nexi — what it is and where the boundary vs xnch lies

## What nexi is

Nexi is the **decision engine** of the xnchSystems agent stack. It is a FastAPI
service (`app = FastAPI(title="Nexi", version="0.1.0")` in `nexi/main.py`) that:

1. Accepts a **resolved session** from xnch (actor already authenticated/resolved).
2. Interprets the raw user input into a structured **Intent**.
3. Loads a **ContextManifest** (recent episodes, learned patterns, active policies) from xnch memory.
4. Generates **PlanOptions** (LLM-constrained or rule-based), filters them through policy dry-run, scores them, simulates top candidates, and selects one.
5. Compiles the selected option into an action spec, gets an execution verdict + token from xnch, and dispatches to an execution runner.
6. Later receives the **outcome callback** from xnch and writes a prediction-delta back to xnch memory.

It is a *decision/policy pipeline with a thin HTTP envelope* — the interesting
logic lives in `nexi/pipeline/` and the models in `nexi/models/`.

## Responsibility boundary vs xnch

| Concern | xnch (control plane) | nexi (decision engine) |
|---------|----------------------|------------------------|
| Auth / actor resolution | Yes — resolves the actor before calling nexi | No — trusts the resolved `actor` in `SessionStartRequest` |
| Memory stores (PG episodic, Redis, graph) | Yes — nexi reads/writes via HTTP | No — nexi only talks to xnch's HTTP endpoints (`/memory/read`, `/memory/write`) |
| Policy evaluation (dry-run) | Yes — `POST /policy/check`, returns verdict per option | No — invokes it per option in parallel |
| Verdict / authorization (final gate) | Yes — `POST /verdict` issues verdict + signed execution token | No — submits and obeys the verdict |
| Execution token issuance | Yes — returned in `VerdictResponse` | No — carries it in the dispatch payload |
| Intent interpretation / classification | No | Yes (`nexi/pipeline/intent_interpreter.py`) |
| Option generation | No | Yes (`option_generator.py`, `ModelAdapter`) |
| Scoring / selection / simulation | No | Yes (`evaluator.py`, `selector.py`) |
| Plan compilation (DAG) | No | Yes (`plan_compiler.py`) |
| Execution dispatch | No (runner is separate) | Yes — posts to `NEXI_EXECUTION_RUNNER_URL/execute` |
| Outcome feedback loop | Yes — stores episode, fires nexi callback | Yes — computes prediction delta and posts `/memory/write` |
| Governance weight profiles | Yes — served at `GET /governance/weights` | No — consumes them (`Evaluator`) |

In short: **xnch owns identity, memory, policy, and audit; nexi owns reasoning**
(intent → options → score → select → dispatch).

## Runtime placement

- nexi runs on **Node B**, typically **:8000**.
- xnch runs on **Node A (gate7)**, **:8001**; nexi reaches it via
  `NEXI_XNCH_BASE_URL` (default `http://localhost:8001`, but in production the
  Node A↔Node B link address `http://192.168.50.1:8001` is used — see
  `NEXI_EXECUTION_RUNNER_URL` default).
- Execution runner: `NEXI_EXECUTION_RUNNER_URL` (default
  `http://192.168.50.1:8001/execution`, i.e. xnch's stub runner). When the
  runner is unreachable, nexi records a stub `SUCCESS` outcome to xnch
  `POST /execution/outcome` instead of failing the session.
- Model serving: LiteLLM proxy (default `http://localhost:4000/v1`), vLLM Ornith
  (health `NEXI_VLLM_HEALTH_URL`), vLLM Qwen-VL (`NEXI_VLLM_PRIMARY_URL`),
  local llama.cpp (`http://localhost:8080`).

## Sub-packages

| Path | Role |
|------|------|
| `nexi/main.py` | FastAPI app + 5 routes (see [endpoints.md](endpoints.md)) |
| `nexi/pipeline/` | Decision stages — see [pipeline.md](pipeline.md) |
| `nexi/models/` | Wire models — see [models.md](models.md) |
| `nexi/adapters/` | `XnchClient` (HTTP to xnch), `ModelAdapter` (LLM routing) |
| `nexi/infra/` | Service discovery (`discovery.py`) — topology/policy snapshot + live probes, backing `/nexi/capabilities` and `/nexi/refresh` |
| `nexi/eval/` | Offline eval harness + CLI |
| `nexi/proactivity/` | Proactivity engine (library, **not** exposed over HTTP) |
| `nexi/character/` | Persona/capabilities/identity-facts prompt assembly + cold-start seeder |
| `nexi/utils/` | Audit emission, context-signature hashing |

## Eval CLI

```
.venv/bin/python -m nexi.eval.cli --fixture
```

- Deterministic offline smoke run over the frozen cases in
  `nexi/eval/cases.yaml` (5 cases: `greeting-direct`, `no-cloud-upsell`,
  `tool-grounded-fs`, `no-auto-kubectl`, `concise-style`).
- Prints JSON `{run_id, results[], mean_score, pass_rate}`.
- Exit code `0` iff `pass_rate == 1.0`, else `1`.
- Only `--fixture` mode is implemented; `--llm-judge` is parsed but the CLI
  raises `SystemExit` unless `--fixture` is given (the LLM-judge path exists in
  `EvalHarness`/`grader.llm_judge`).
- `nexi/eval/store.py::persist_eval_run` writes scores into PG via
  `PgEpisodicStore.store_eval_run` (loop-4 signal path) — not used by the CLI.

## Notes / TODOs

- **`ClarifyRequest`** (`nexi/main.py:81`) is defined but **no route uses it** —
  it appears intended for a clarification endpoint that does not exist yet.
- `/nexi/voice/chat` is referenced in `nexi/character/capabilities.yaml`
  (persona text) but is **not defined in `nexi/main.py`** — it is served
  elsewhere (likely xnch). TODO: confirm actual owner.
- `nexi/pipeline/context_assembler.py` builds chat system prompts from memory
  (working memory, PG recall, graph entities, relationships, sensory voice
  buffer). It is **not** on the `/session/start` decision path.
- `nexi/policies/default.yaml` ships baseline governance rules (weekend-deploy
  block, agent rate, viewer read-only, etc.) but the live policy evaluation
  lives on the **xnch** side (`/policy/check`).
