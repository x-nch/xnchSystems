# XNCH / Nexi

Private AI orchestration platform. One man's infrastructure for autonomous agents. Solo-built, production-deployed on a two-node Kubernetes cluster. No cloud dependency for inference.

XNCH is the control plane (platform layer). Nexi is the product layer. Together they form a complete decision-and-memory system for an AI that perceives the world, remembers what matters, reasons about what to do, and acts — on its own hardware, under its own governance.

The codebase is a Python monorepo with two FastAPI services (Python 3.13+), Kubernetes deployment manifests, YAML policy definitions, scoring weights, and documentation. Everything runs on two physical nodes labeled i7 and i9.

---

## Platform vs Product

**XNCH** (`xnch/`) is the platform layer: governance, memory, authorization, policy enforcement, perception, audit, and learning. It runs on the i7-memory node. Entrypoint is `xnch/xnch/main.py`. It owns the data, the secrets, the policies, and the historical record. Configuration is driven by environment variables prefixed `XNCH_*`.

**Nexi** (`nexi/`) is the product layer: decision engine, character and persona, LLM orchestration, proactivity, and context assembly. It runs on the i9-inference node. Entrypoint is `nexi/nexi/main.py`. It owns the model calls, the plan options, the execution pipeline. Configuration is driven by environment variables prefixed `NEXI_*`.

The two services communicate over HTTP:
- Nexi calls xnch at `NEXI_XNCH_BASE_URL` (default `http://localhost:8001`) for policy checks, memory reads, and verdicts.
- xnch calls Nexi at `XNCH_NEXI_BASE_URL` (default `http://localhost:8000`) for session start and outcome callbacks.
- They share a Redis instance — xnch connects over TCP, Nexi connects over a Unix socket (`/tmp/xnch-redis.sock`).

---

## Hardware Topology

Two physical nodes, each with a dedicated role enforced via Kubernetes node labels.

### i7-node (label `role=memory`)

| Service | Port | Purpose |
|---|---|---|
| PostgreSQL 15 + pgvector | 5432 | Episodic store, relationship store, quarantine store. 50Gi PVC via StatefulSet. |
| Redis | 6379 (TCP) | KV cache, sensory buffer (L0), working memory (L1), session dedup, rate limiting. |
| Langfuse | 3000 | LLM observability and tracing. |
| LiteLLM proxy | 4000 | Model routing gateway for local and cloud LLMs. |
| xnch server | 8001 | Control plane API, governance, policy engine, audit. |
| Perception daemonset | — | Voice capture (Whisper), vision (Moondream2), file watching, attention signals. |

### i9-node (label `role=inference`)

| Service | Port | Purpose |
|---|---|---|
| vLLM + Gemma 4 26B | 8000 | Primary inference engine (~135 tok/s on RTX 3090). |
| Nexi decision engine | 8001 | Pipeline: context assembly, option gen, scoring, selection, plan compilation. |
| mem0 | — | Long-term agent memory layer. |
| Zep | — | Long-term memory persistence and summarization. |

---

## Quickstart

### Prerequisites

- k3s or Kubernetes cluster with two nodes and `kubectl` configured.
- Nodes labeled correctly: `i7-node` with `role=memory`, `i9-node` with `role=inference`.
- Secrets created in the `xnch-system` namespace.

### First Boot

```bash
# Label nodes
kubectl label node i7-node role=memory
kubectl label node i9-node role=inference

# Create secrets (replace placeholder values)
kubectl create secret generic postgres-secret -n xnch-system \
  --from-literal=password='<your-pw>'
kubectl create secret generic xnch-secret -n xnch-system \
  --from-literal=auth_secret='<secret>'
kubectl create secret generic litellm-secret -n xnch-system \
  --from-literal=master_key='<key>'
kubectl create secret generic langfuse-secret -n xnch-system \
  --from-literal=nextauth_secret='<secret>' --from-literal=salt='<salt>'
kubectl create secret generic huggingface-secret -n xnch-system \
  --from-literal=token='<hf-token>'

# Deploy in dependency order
kubectl apply -f deploy/k8s/namespaces.yaml
kubectl apply -f deploy/k8s/i7-node/
kubectl apply -f deploy/k8s/i9-node/
kubectl apply -f deploy/k8s/jobs/

# Verify everything is running
kubectl get all -n xnch-system
kubectl get pods -n xnch-system -o wide
```

### Verify Nexi Is Live

```bash
# Nexi health endpoint
curl http://<nexi-svc>:8001/health

# xnch health endpoint (includes Redis state)
curl http://<xnch-svc>:8000/health

# Expected healthy response from xnch
# {"status": "ok", "redis": "ok", "state_version": "v1.45.0", "version": "0.1.0"}
```

### Development (local, no cluster)

```bash
# Start Redis
redis-server &

# Start xnch (postgres required)
uv run python -m xnch.main

# Start nexi (requires xnch running)
uv run python -m nexi.main
```

Persistent volume claims are created automatically: `xnch-data` for the xnch server, `xnch-vault` for the perception daemonset, and `pgdata` (50Gi) for PostgreSQL via its StatefulSet.

---

## Repository Layout

```
nexi/                              Execution engine — FastAPI, decision pipeline, LLM orchestration
  nexi/main.py                     App entrypoint, /session/start, /callback/outcome
  nexi/config.py                   NEXI_* environment variable definitions
  nexi/character/                  Nexi persona YAML, cold start seeder, system prompt loader
  nexi/pipeline/                   Intent interpreter, context assembler, option generator,
                                   policy filter, evaluator, selector, plan compiler, dispatch
  nexi/models/                     Pydantic models: intent, session, DAG, options, outcomes
  nexi/adapters/                   ModelAdapter (LiteLLM + vLLM + llama.cpp fallback), XnchClient
  nexi/proactivity/                ProactivityEngine — pattern/consolidation/inference/learning alerts
  nexi/utils/                      Audit helper, context signature
xnch/                              Control plane — FastAPI, governance, memory, auth, policy, learning
  xnch/main.py                     App entrypoint, lifespan wiring, scheduler registration
  xnch/config.py                   XNCH_* environment variable definitions
  xnch/routes/                     Session, memory, policy, verdict, execution, governance, auth, nexi_gateway
  xnch/auth/                       RSA key pair generation, TokenSigner/Verifier, GovernanceStore
  xnch/security/                   Trust model, injection guard, actor sandbox, memory write guard
  xnch/memory/                     Sensory buffer (Redis), working memory (Redis), episodic store
                                   (pgvector), pattern store (SQLite), graph store (agentmemory),
                                   relationship store (PG), quarantine store (PG), KV cache (Redis),
                                   database migrations
  xnch/policy/                     YAML policy loader, policy engine (first-match-wins)
  xnch/learning/                   Pattern extractor, score adapter, policy candidate generator
  xnch/perception/                 Voice daemon, vision encoder, file watcher, attention filter
  xnch/routing/                    Model classifier — routes to gemma4-local or claude-judgment
  xnch/audit/                      EventLog (append-only JSONL), DecisionLedger (SHA-256 chain)
  xnch/observability/              Langfuse client for LLM call tracing
  xnch/jobs/                       Consolidation job (daily CronJob)
deploy/                            K8s manifests, Dockerfiles, infrastructure configuration
  k8s/i7-node/                     PostgreSQL, Redis, Langfuse, LiteLLM, xnch, perception daemonset
  k8s/i9-node/                     vLLM, Nexi, mem0, Zep
  k8s/jobs/                        Consolidation CronJob, vault indexer
  docker/                          xnch.Dockerfile, nexi.Dockerfile
  openclaw/                        OpenClaw client config, start_nexi.sh
policies/                          YAML policy definitions (default.yaml, custom.yaml)
weights/                           Scoring weight configs per intent class
docs/                              Architecture docs, operations guide, security reference
```

---

## Environment Variables

### XNCH_* — Control Plane Configuration (20 vars)

Defined in `xnch/xnch/config.py`.

| Variable | Default | Description |
|---|---|---|
| `XNCH_BASE_DIR` | `~/.xnch` | Root data directory; contains `keys/`, `audit/`, `governance/`, `policies/`, `weights/` |
| `XNCH_REDIS_URL` | `redis://localhost:6379/0` | Redis connection for KV cache, sensory buffer, working memory |
| `XNCH_AUTH_SECRET` | `dev-secret-change-in-production` | Shared secret for HS256 bearer token verification |
| `XNCH_TOKEN_TTL_MS` | `30000` | Default execution token TTL in milliseconds |
| `XNCH_SESSION_TTL_S` | `120` | Session TTL in seconds |
| `XNCH_RATE_LIMIT_PER_MINUTE` | `10` | Max requests per minute per actor |
| `XNCH_NEXI_BASE_URL` | `http://localhost:8000` | Nexi service callback URL |
| `XNCH_POSTGRES_URL` | `postgresql://localhost:5432/xnch` | PostgreSQL + pgvector connection string |
| `XNCH_PATTERN_MIN_OBSERVATIONS` | `10` | Minimum episodes before pattern extraction triggers |
| `XNCH_SCORE_ADAPTER_ACCURACY_THRESHOLD` | `0.6` | Minimum accuracy before score adaptation triggers |
| `XNCH_LANGFUSE_PUBLIC_KEY` | `""` | Langfuse public key for observability (empty = disabled) |
| `XNCH_LANGFUSE_SECRET_KEY` | `""` | Langfuse secret key (empty = disabled) |
| `XNCH_LANGFUSE_HOST` | `https://cloud.langfuse.com` | Langfuse API host |
| `XNCH_LITELLM_PROXY_URL` | `http://litellm:4000` | LiteLLM proxy base URL |
| `XNCH_GRAPH_EXTRACTOR_MODEL` | `ollama/phi3:mini` | Model used for entity-relation extraction from episodes |
| `XNCH_VAULT_DIR` | `~/.xnch/vault` | Perception vault directory for file watching |
| `XNCH_PERCEPTION_REDIS_DB` | `0` | Redis DB used for perception signals |
| `XNCH_ATTENTION_SILENCE_THRESHOLD_S` | `1.5` | Seconds of silence before voice input triggers an action |
| `XNCH_ATTENTION_SCREEN_DIFF_THRESHOLD` | `0.15` | Pixel-diff fraction for screen-change detection |
| `XNCH_ATTENTION_IDLE_TIMEOUT_S` | `600` | Seconds idle before memory consolidation triggers |

### NEXI_* — Execution Engine Configuration (18 vars)

Defined in `nexi/nexi/config.py`.

| Variable | Default | Description |
|---|---|---|
| `NEXI_XNCH_BASE_URL` | `http://localhost:8001` | xnch control plane API base URL |
| `NEXI_XNCH_PUBLIC_KEY_PATH` | `~/.xnch/keys/public.pem` | Path to xnch's RS256 public key for token verification |
| `NEXI_VLLM_PRIMARY_URL` | `http://localhost:8000/v1` | Primary vLLM inference endpoint |
| `NEXI_VLLM_PRIMARY_TIMEOUT_S` | `30.0` | Primary vLLM request timeout |
| `NEXI_VLLM_SECONDARY_URL` | `""` | Secondary vLLM endpoint (fallback, empty = disabled) |
| `NEXI_VLLM_SECONDARY_TIMEOUT_S` | `45.0` | Secondary vLLM request timeout |
| `NEXI_MODEL_ID` | `mistralai/Mistral-7B-Instruct-v0.3` | Default model identifier |
| `NEXI_OPTIONS_COUNT` | `5` | Number of plan options generated per intent |
| `NEXI_LITELLM_PROXY_URL` | `http://localhost:4000/v1` | LiteLLM proxy endpoint for chat completions |
| `NEXI_LITELLM_PROXY_TIMEOUT_S` | `60.0` | LiteLLM proxy request timeout |
| `NEXI_INTENT_CLASSIFIER_MODEL` | `gemma4-local` | Model used for intent classification |
| `NEXI_SESSION_TTL_S` | `120` | Session TTL in seconds |
| `NEXI_CLARIFICATION_TTL_S` | `120` | Clarification sub-session TTL |
| `NEXI_EXECUTION_TOKEN_TTL_MS` | `30000` | Execution token validity in milliseconds |
| `NEXI_REDIS_URL` | `unix:///tmp/xnch-redis.sock` | Shared Redis connection (Unix socket, same instance xnch uses) |
| `NEXI_EXECUTION_RUNNER_URL` | `http://localhost:8002` | Execution runner service URL |
| `NEXI_VLLM_HEALTH_URL` | `http://vllm-gemma4:8000/health` | vLLM health endpoint (used by proactivity engine) |
| `NEXI_AUDIT_EVENTS_PATH` | `~/.xnch/audit/events.jsonl` | Audit event log file path |

### No-Prefix — nexi_gateway Configuration (2 vars)

Used by the nexi_gateway route in xnch for LiteLLM relay.

| Variable | Default | Description |
|---|---|---|
| `LITELLM_BASE_URL` | `http://i7-node:4000` | LiteLLM proxy URL for chat completions |
| `LITELLM_API_KEY` | `""` | LiteLLM API key (empty = no auth) |

---

## Running Tests

```bash
pytest                      # All tests (auto-asyncio mode)
pytest nexi/tests           # Nexi tests only
pytest xnch/tests           # xnch tests only
pytest nexi/tests/test_evaluator.py  # Single test file
```

No dedicated lint or typecheck commands exist in this repository.
