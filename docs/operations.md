# Operations

Operational procedures for the XNCH/Nexi private AI orchestration platform. Intended for on-call engineers, platform operators, and anyone debugging the system in production.

- [Daily Consolidation Job](#daily-consolidation-job)
- [Background Cron Jobs](#background-cron-jobs)
- [System Health Checks](#system-health-checks)
- [Langfuse Traces](#langfuse-traces)
- [Redis Working Memory Inspection](#redis-working-memory-inspection)
- [PostgreSQL Store Queries](#postgresql-store-queries)
- [SQLite Store Inspection](#sqlite-store-inspection)
- [Glossary](#glossary)

---

## Daily Consolidation Job

Every night at 2 AM, a Kubernetes CronJob (`deploy/k8s/jobs/consolidation-cronjob.yaml`) runs `run_consolidation()` from `xnch/jobs/consolidation.py`. The job performs three operations in sequence.

**Summarization.** The 100 most recent episodes are fetched from agentmemory and forwarded to Zep, which handles LLM summarization internally. The system treats Zep as a black box — no prompt tuning or model selection is exposed at this layer.

**Graph extraction.** The same recent episodes are passed to `extract_and_store()` in `xnch/memory/graph_extractor.py`, which uses an LLM to identify entity-relation triples — subject–predicate–object extractions like "ck-san requested deployment on resource cluster-x." The extractor model is configured via `XNCH_GRAPH_EXTRACTOR_MODEL` and defaults to `ollama/phi3:mini`. Extracted triples are written to the RelationshipStore (PostgreSQL). The function returns a count of triples inserted.

**Decay recomputation and archival.** Up to 5000 episodes are fetched via `get_memories()`. For each episode, a decay score is recomputed:

```
decay = importance * e^(-0.1 * days_since_creation) * (1 + 0.1 * recall_count)
```

If the decay score falls below 0.1 and the episode is not already archived, its metadata is set to `archived = True`. Archived episodes are de-prioritized in similarity searches but remain accessible by direct lookup.

The job logs `"Consolidation complete — N episodes archived"` on success or `"Consolidation failed"` with the exception on failure.

To force an off-schedule run:

```bash
kubectl create job --from=cronjob/consolidation-cronjob manual-consolidation-1 \
  -n xnch-system
```

---

## Background Cron Jobs

Three jobs run every 6 hours via APScheduler, registered in `xnch/main.py`:

| Scheduler ID | Cron | Purpose |
|---|---|---|
| `pattern_extractor` | `hour="*/6"` | Extracts and scores behavioural patterns from completed episodes |
| `score_adapter` | `hour="*/6", minute=30` | Monitors prediction accuracy drift and proposes weight tuning |
| `policy_candidates` | `hour="*/6", minute=45` | Generates YAML policy rule candidates from low-success patterns |

### PatternExtractor

Runs at minute 0 of every 6th hour. Queries episodes since the last run, groups them by (intent_class, action_type, entity_class, actor_role), and computes a Bayesian-smoothed success rate for each group. Results are upserted into the PatternStore (SQLite), which the policy engine consults during evaluation. This is the mechanism by which the system learns which action sequences tend to succeed or fail in which contexts. Minimum observation threshold is configurable via `XNCH_PATTERN_MIN_OBSERVATIONS` (default 10).

### ScoreAdapter

Runs at minute 30 of every 6th hour. Compares prediction accuracy over two rolling windows: the last 7 days versus the last 30 days, per scoring dimension. When the drift exceeds 0.05, the adapter auto-proposes adjustments to the weight configuration. The proposals are written but not applied automatically — a human or supervisory process must confirm them. Accuracy threshold is configurable via `XNCH_SCORE_ADAPTER_ACCURACY_THRESHOLD` (default 0.6).

### PolicyCandidateGenerator

Runs at minute 45 of every 6th hour. Reads patterns with low success rates (< 0.4) but high confidence (> 0.5) — patterns the system is sure fail reliably. It then calls the LLM designated `claude-judgment` to produce YAML policy DSL candidates that would block or modify those failing behaviours. Candidates are written to the `policy_candidates` table for review. The intent is to tighten the policy surface over time as the system observes which behaviours consistently underperform.

---

## System Health Checks

### Kubernetes Cluster State

All services run in the `xnch-system` namespace. Start here when something feels wrong:

```bash
# Everything at a glance
kubectl get all -n xnch-system

# Pod placement and node assignment
kubectl get pods -n xnch-system -o wide

# Service endpoints and ClusterIPs
kubectl get svc -n xnch-system

# Persistent volume claims
kubectl get pvc -n xnch-system
```

### Service Logs

Logs are labelled by application. Each core service has its own selector:

```bash
kubectl logs -n xnch-system -l app=xnch-server
kubectl logs -n xnch-system -l app=nexi
kubectl logs -n xnch-system -l app=litellm
kubectl logs -n xnch-system -l app=vllm
```

For a failing pod, `describe` surfaces resource limits, liveness probe failures, and recent container restarts:

```bash
kubectl describe pod -n xnch-system <pod-name>
```

### Local Port Forwarding

For debugging against a live cluster without deploying a local copy:

```bash
kubectl port-forward -n xnch-system svc/xnch-server 8001:8001
kubectl port-forward -n xnch-system svc/nexi 8001:8000
kubectl port-forward -n xnch-system svc/redis 6379:6379
```

### Health Endpoints

The xnch server exposes a health check at `/health`:

```bash
curl http://localhost:8001/health
```

A healthy response:

```json
{"status": "ok", "redis": "ok", "state_version": "v1.45.0", "version": "0.1.0"}
```

If Redis is unreachable, the response changes to `"degraded"` and the `redis` field reads `"unavailable"`. The server continues serving requests but working memory operations are impaired.

### Redis Ping

Redis is used by both services. xnch connects over TCP, Nexi connects over a Unix socket:

```bash
# Via TCP (xnch's connection)
redis-cli -h localhost -p 6379 ping

# Via Unix socket (Nexi's connection)
redis-cli -s /tmp/xnch-redis.sock ping
```

Both should return `PONG`.

### System State

The `/system/state` endpoint returns current configuration versions:

```bash
curl http://localhost:8001/system/state
```

```json
{"system_state_version": "v1.45.0", "policy_version": "v2"}
```

These versions are useful for correlating behaviour against deployment history — a mismatch between `state_version` on the health endpoint and the expected release version typically indicates a stale deployment or failed rollout.

---

## Langfuse Traces

LLM call tracing is wired through the `LangfuseClient` in `xnch/observability/langfuse_client.py`. The client POSTs to `/api/public/ingestion` on the configured Langfuse host (defaults to `https://cloud.langfuse.com`). A local Langfuse instance can be deployed via `deploy/k8s/i7-node/langfuse.yaml`.

### Authentication

The client uses HTTP Basic auth with `public_key:secret_key`, sourced from `XNCH_LANGFUSE_PUBLIC_KEY` and `XNCH_LANGFUSE_SECRET_KEY`. If both keys are empty strings, the client returns `None` silently — no tracing occurs and no error is raised. This is the intended mechanism for disabling tracing in development or air-gapped deployments.

### Trace API

```python
trace_llm_call(
    prompt,         # The input sent to the model
    response,       # The model's output
    model,          # Model identifier string
    latency_ms,     # Round-trip latency in milliseconds
    tokens_used,    # Token count (input + output)
    trace_id=None   # Optional; defaults to generation ID
)
```

### What Gets Traced

Two call sites emit traces:

- **`model_adapter.py`** — every LiteLLM and llama.cpp call made during option generation is traced with the model name as seen in configuration (e.g., `gemma4-local`, `llama-cpp`).
- **`verdict.py`** — every policy verdict (BLOCK or ALLOW) is traced as a model call under the name `policy-engine`.

### Viewing Traces

Open the Langfuse dashboard and search by `trace_id`. The trace ID is typically the `session_id` from the original request, making it straightforward to correlate traces back to user-facing interactions. Filtering by model name is the fastest way to isolate a specific subsystem: `gemma4-local` for generation, `claude-judgment` for policy evaluation, `policy-engine` for verdicts.

---

## Redis Working Memory Inspection

Redis holds ephemeral session state. The connection method differs between the two services: xnch uses TCP (port 6379), Nexi uses a Unix socket (`/tmp/xnch-redis.sock`).

### Connecting

```bash
# Over TCP (xnch)
redis-cli -h localhost -p 6379

# Over Unix socket (Nexi)
redis-cli -s /tmp/xnch-redis.sock
```

### Key Patterns

| Pattern | Contents |
|---|---|
| `session:{session_id}:turns` | Turn history for a session (Redis list) |
| `session:{session_id}:{key}` | Arbitrary context fields for a session (Redis hash) |
| `perception:{source}:{uuid}` | Active perception signals (TTL 60s) |
| `proactivity:pending:{uuid}` | Events queued for proactive dispatch |
| `ratelimit:*` | Rate-limit counters and windows |
| `nexi:system-prompt` | Cached system prompt (TTL 60s) |

### Common Inspection Commands

```bash
# List active sessions
KEYS "session:*"

# Inspect a session's turn history
LRANGE session:<session_id>:turns 0 -1

# Inspect a session's context fields
HGETALL session:<session_id>:context

# Check what the system is sensing
KEYS "perception:*"

# See what proactivity events are queued
KEYS "proactivity:pending:*"
GET proactivity:pending:<uuid>

# View the cached system prompt
GET nexi:system-prompt

# Rate limit state
KEYS "ratelimit:*"

# Check session TTL
TTL session:<session_id>:turns
```

If a session appears to be missing context, start with `HGETALL` on its registered keys. If turns are truncated unexpectedly, check `LLEN` against the configured maximum turn depth (default 20). If rate limits are triggering incorrectly, dump the relevant `ratelimit:*` key.

---

## PostgreSQL Store Queries

The episodic store, relationship store, and quarantine store all live in PostgreSQL 15 with pgvector.

### Connecting

```bash
psql postgresql://localhost:5432/xnch
```

### Useful Queries

```sql
-- Strongest entity relationships
SELECT * FROM relationship_memory ORDER BY strength DESC LIMIT 20;

-- Most recall episodes
SELECT id, type, summary, importance, recall_count, decay_score
FROM episodic_memory
ORDER BY recall_count DESC
LIMIT 20;

-- Recently stored episodes (non-identity)
SELECT id, type, raw_text, created_at
FROM episodic_memory
WHERE type != 'identity'
ORDER BY created_at DESC
LIMIT 10;

-- Archived episodes (decayed below threshold)
SELECT id, type, summary, decay_score
FROM episodic_memory
WHERE archived = true
ORDER BY decay_score ASC
LIMIT 20;

-- Memories under quarantine (blocked from recall)
SELECT * FROM quarantine_memories
WHERE released_at IS NULL
ORDER BY created_at DESC;

-- Entity graph for a specific entity
SELECT * FROM relationship_memory
WHERE entity_a_id = 'ck-san' OR entity_b_id = 'ck-san'
ORDER BY strength DESC;
```

The `quarantine_memories` table is worth checking when recall quality deteriorates — a backlog of unreleased quarantine entries can indicate a stuck release process or a manual review bottleneck.

---

## SQLite Store Inspection

The PatternStore, GovernanceStore, and weight configurations are stored in SQLite files under `~/.xnch/`.

### Connecting

```bash
# Pattern store
sqlite3 ~/.xnch/patterns.db

# Governance store
sqlite3 ~/.xnch/governance.db

# Weights
sqlite3 ~/.xnch/weights.db
```

### Pattern Store Queries

```sql
-- All learned patterns
SELECT * FROM patterns;

-- Lowest success patterns (likely candidates for policy update)
SELECT * FROM patterns
WHERE success_rate < 0.4
ORDER BY success_rate ASC;

-- Most confident patterns
SELECT * FROM patterns
WHERE confidence > 0.8
ORDER BY confidence DESC;

-- Patterns by intent class
SELECT intent_class, COUNT(*) as count,
       AVG(success_rate) as avg_success,
       AVG(confidence) as avg_confidence
FROM patterns
GROUP BY intent_class;
```

### Governance Store Queries

```sql
-- All registered actors
SELECT * FROM actors;

-- Actors with their capabilities
SELECT name, role, capability_set FROM actors;

-- Policy candidates awaiting review
SELECT * FROM policy_candidates
ORDER BY created_at DESC;
```

### Weight Config Queries

```sql
-- Weight configs by intent class
SELECT * FROM weight_configs
WHERE intent_class = 'DECISION';

-- Compare weights across intent classes
SELECT intent_class, dimension, weight
FROM weight_configs
ORDER BY intent_class, weight DESC;
```

---

## Glossary

| Term | Meaning |
|---|---|
| **Episode** | A single recorded interaction or observation in the agent's memory. The atomic unit of experience. |
| **Decay** | A computed score (0 to 1) representing how relevant an episode remains. Episodes below 0.1 are archived. |
| **RelationshipStore** | PostgreSQL-backed store for entity-relationship strength tracking with reinforcement counting. |
| **PatternStore** | SQLite-backed store for behavioural patterns with Bayesian-smoothed success rates. |
| **PolicyCandidate** | A proposed YAML policy rule generated by LLM from low-success patterns, awaiting review. |
| **agentmemory** | The memory abstraction layer (ChromaDB-compatible) used for episode storage and similarity search. |
| **Proactivity** | The system's ability to initiate actions without a direct user request, based on learned patterns and system health. |
| **Zep** | External summarization service that condenses recent episodes into narrative memory summaries. |
| **DecisionLedger** | SHA-256 chained, append-only, tamper-evident log of every policy verdict issued by xnch. |
| **EventLog** | Append-only JSONL file recording all system events with timestamp, level, component, and trace context. |
