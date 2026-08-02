# Architecture Overview

XNCH is the control plane. Nexi is the execution engine. Together they form a private AI orchestration platform that runs on two dedicated machines — a memory node and an inference node — with no external cloud dependency for inference. The system is built around a four-layer memory hierarchy, a trust-gated request lifecycle, a 14-step decision pipeline, and a hardware partition that separates state from computation.

This document describes every moving part, how they connect, and why they are arranged this way.

---

## Four-Layer Memory System

Memory is the central architectural concern. Rather than a single store, the system uses four layers with decreasing speed and increasing permanence. A warm path serves fast, session-local reads. A cold path engages only when the warm context is insufficient.

### Layer 0 — Sensory Buffer (Redis)

The sensory buffer holds raw perception signals with automatic TTL expiry, defaulting to sixty seconds. Three types of signal enter this layer: voice transcripts produced by Whisper, vision descriptions produced by Moondream2, and file system events. Each signal is stored under a key of the form `perception:{source}:{uuid}`, and its payload is a JSON object carrying the source identifier, the signal data, and a timestamp.

The buffer exposes four operations. `write_perception(source, data, ttl=60)` stores a signal. `read_recent(source, limit=10)` returns the N most recent signals for a given source, ordered by timestamp. `flush_to_working_memory(key, summary, working_memory, session_id)` promotes a signal into Layer 1, attaching a summary and targeting a specific session. A delete operation rounds out the interface.

### Layer 1 — Working Memory (Redis)

Working memory is organized per session. Each session has a TTL of one hour by default (configurable via `SESSION_TTL_S`). The key space splits into two patterns: `session:{session_id}:turns` (a Redis list tracking conversation turn history) and `session:{session_id}:{key}` (hash fields holding arbitrary session variables).

`set_context(session_id, key, value)` and `get_context(session_id, key)` provide key-value storage within a session. `append_turn(session_id, role, content)` pushes a message onto the turn list, marking it as either user or assistant. `get_turns(session_id, last_n=20)` retrieves the most recent N turns. `get_full_session(session_id)` scans all keys for a session and returns the entire context as a dictionary. `clear_session(session_id)` deletes all keys associated with the session.

### Layer 2 — Episodic Store (PostgreSQL + pgvector via agentmemory)

Long-term episodic memory lives in PostgreSQL with the pgvector extension for vector similarity search, backed by agentmemory (ChromaDB-compatible) for vector indexing. This layer remembers what happened across all sessions, not just the current one.

`store_episode(type_, raw_text, summary, importance)` inserts a record into PostgreSQL and agentmemory simultaneously. Metadata includes: type, raw_text, summary, importance, recall_count, archived flag, decay score, and timestamp. `retrieve_similar(query_text, top_k)` performs cosine similarity search via agentmemory to find the most relevant past episodes. `get_recent_episodes(limit)` returns the most recent episodes regardless of relevance. Recall bumping increments `recall_count` each time an episode is retrieved via semantic search.

Alongside the episode store sits a PatternStore implemented in SQLite. Every six hours a PatternExtractor runs Bayesian-smoothed success rate analysis across episodes, grouped by a context tuple of (intent_class, action_type, entity_class, actor_role). The resulting patterns inform routing and proactivity decisions without requiring real-time queries against raw episode data.

### Layer 3 — Graph Store (agentmemory categories + PostgreSQL relationships)

The graph store captures relationships between entities. Two stores collaborate here. The RelationshipStore in PostgreSQL uses a `relationship_memory` table with columns for entity_a_id, entity_b_id, relationship_type, strength (a float), and reinforcement_count. Strength increases on repeated co-occurrence. The GraphStore in agentmemory holds entities and relation categories for broader traversal.

Entities and their relationships are extracted from episodes by an LLM-powered graph extractor. The extractor uses a configurable model, defaulting to `ollama/phi3:mini` via `XNCH_GRAPH_EXTRACTOR_MODEL`. The extraction produces entity-relation triples of the form subject–predicate–object. Once stored, relationships can be queried via `get_relationship_strength(entity_a, entity_b)`, which returns a float, and `get_relationships(entity_id)`, which returns all relationships for a given entity.

### Warm vs Cold Path

The warm path comprises Layers 0 and 1, both in Redis. Sensory signals have a TTL measured in seconds; working memory has a TTL of one hour. Reads against these layers complete in under a millisecond and never touch PostgreSQL. The cold path comprises Layers 2 and 3. A pgvector similarity search takes 50 to 200 milliseconds. A graph traversal takes 100 to 500 milliseconds. The system prefers the warm path for every request and only falls through to the cold path when the assembled warm context is insufficient — for instance, when a user asks a question that requires recalling a fact from a conversation days ago.

---

## Request Lifecycle (Chat)

Every interactive request enters through a single endpoint: `POST /nexi/chat`. OpenClaw sends a JSON body containing a session_id, a message, and an actor_role. The request passes through seven stages before a response is returned.

**1. Injection scan.** `scan_input` applies nine compiled regular expression patterns to the incoming message. If any pattern matches — attempts to override the system prompt, reassign the agent role, or inject jailbreak keywords — the endpoint returns a 400 status with the message "Input rejected by injection guard." No further processing occurs.

**2. Context assembly.** `assemble_context()` fetches data from all four memory layers. From Layer 0: recent voice perceptions via the SensoryBuffer. From Layer 1: the last 20 working memory turns via Redis. From Layer 2: relevant episodes via pgvector similarity search (top 5 by cosine similarity). From Layer 3: entity context from GraphStore and RelationshipStore. It also fetches the system prompt via `build_system_prompt(session_memory, recent_entities)` and any pending proactivity observations. The result is a ContextManifest whose `to_messages(message)` method converts the assembled context into message dictionaries suitable for LLM consumption.

**3. Model classification.** `classify_request()` routes the request to the appropriate model. Three rules apply: privacy-sensitive inputs go to gemma4-local; EXECUTION intents go to gemma4-local; DECISION intents with complexity score above 0.7 go to claude-judgment (a cloud model). All other cases default to gemma4-local. Past routing decisions are cached in agentmemory so the classifier can short-circuit if it has seen the same input before.

**4. LLM call.** The LiteLLM proxy on port 4000 of the i7-node relays the request. If the model is gemma4-local, the proxy forwards to the vLLM instance on the i9-node's RTX 3090 (~135 tokens per second). If the model is claude-judgment, the proxy forwards to the Anthropic API. The call uses `max_tokens=2048`, `temperature=0.7`.

**5. Response handback.** The LLM response travels back through the LiteLLM proxy to xnch, which returns it to OpenClaw.

**6. Memory write.** The response is appended to the working memory turn list via `append_turn`. Then the memory guard validates the write: `validate_memory_write()` checks injection scan pass AND trust level >= TRUSTED_AGENT. If the guard passes, the interaction is stored as an episode in pg_episodic via `store_episode`.

**7. Cache invalidation.** The system prompt cache is invalidated (`redis.delete("nexi:system-prompt")`) so that subsequent requests receive fresh context reflecting the just-completed interaction.

---

## Decision Pipeline (Session Start)

When Nexi initiates a session (not a simple chat, but a full decision flow for execution), it passes through 14 steps spanning both services. Steps 1–2 run in xnch; steps 3–11 run in Nexi; steps 12–14 cross the boundary again.

| Step | What Happens | Where |
|---|---|---|
| 1 | **Session init.** Authentication, session deduplication, rate limiting check. | xnch |
| 2 | **Session start.** Nexi is notified via `POST /callback/session/start`. | xnch → Nexi |
| 3 | **Intent interpretation.** Rule-based classification into four intent classes: QUERY, DECISION, EXECUTION, ESCALATION. Falls back to LLM if rules are inconclusive. | Nexi |
| 4 | **Context manifest load.** Nexi fetches context from xnch via `GET /memory/read`. | Nexi → xnch |
| 5 | **Weight config fetch.** Nexi retrieves scoring weights from xnch via `GET /governance/weights`. | Nexi → xnch |
| 6 | **Option generation.** Tries LiteLLM, then falls through to vLLM primary, then llama.cpp, then rule-based templates. Produces N options (configurable via `NEXI_OPTIONS_COUNT`, default 5). | Nexi |
| 7 | **Policy filter.** Each option is checked against xnch policy engine in parallel via `POST /policy/check`. Options that fail policy are discarded. | Nexi → xnch |
| 8 | **Scoring.** Remaining options are scored across four weighted dimensions: policy compliance, predicted outcome, execution risk, and context fit. Weights are per intent class. | Nexi |
| 9 | **Outcome simulation.** For high-impact options, a simulation is run and scores are adjusted. Conditional — skipped for low-risk options. | Nexi |
| 10 | **Selection.** The highest-scored option is selected. | Nexi |
| 11 | **Plan compilation.** The selected option is compiled into a directed acyclic graph (DAG) of execution steps. | Nexi |
| 12 | **Verdict.** Nexi sends the compiled plan to xnch via `POST /verdict`. xnch performs an authoritative re-evaluation, issues an RS256 execution token if the verdict is ALLOW or BLOCK, and writes the decision to the DecisionLedger (SHA-256 chained, tamper-evident). | Nexi → xnch |
| 13 | **Execution dispatch.** The execution token and compiled DAG are sent to the execution-runner service. | Nexi |
| 14 | **Outcome callback.** Execution-runner calls xnch `POST /execution/outcome`, which forwards to Nexi `POST /callback/outcome`. On Nexi, a prediction delta is computed; if delta > 0.3, an early graph re-extraction is triggered and the delta is written to memory. | execution-runner → xnch → Nexi |

---

## Trust Model

Every actor that touches the system carries a trust level. Five levels exist, from the most trusted to the least.

| Level | Value | Meaning |
|---|---|---|
| UNTRUSTED | 1 | Unknown or explicitly external actors. Default for any unmapped role. |
| EXTERNAL_AGENT | 2 | Third-party agent integrations (future). No writes or job triggers. |
| TRUSTED_AGENT | 3 | Known system agents: opencode, perception_daemon, consolidation_job. |
| OWNER | 4 | The human operator. |
| SYSTEM | 5 | The nexi engine itself. Full capabilities. |

### Actor-to-Trust Mapping

| Actor | Level |
|---|---|
| nexi | SYSTEM (5) |
| admin | OWNER (4) |
| operator | OWNER (4) |
| agent | TRUSTED_AGENT (3) |
| viewer | EXTERNAL_AGENT (2) |
| opencode | TRUSTED_AGENT (3) |
| perception_daemon | TRUSTED_AGENT (3) |
| consolidation_job | TRUSTED_AGENT (3) |
| external | UNTRUSTED (1) |
| *any unmapped* | UNTRUSTED (1) |

### Capability Grid

| Capability | SYSTEM | OWNER | TRUSTED | EXTERNAL | UNTRUSTED |
|---|---|---|---|---|---|
| can_write_memory | ✓ | ✓ | ✓ | ✗ | ✗ |
| can_read_all_memory | ✓ | ✓ | ✗ | ✗ | ✗ |
| can_trigger_jobs | ✓ | ✓ | ✓ | ✗ | ✗ |
| can_modify_policies | ✓ | ✗ | ✗ | ✗ | ✗ |
| can_access_perception | ✓ | ✓ | ✗ | ✗ | ✗ |

Trust levels are enforced through two mechanisms. The `@requires_trust(minimum)` decorator reads the `X-Actor-Role` header from incoming requests, looks up the actor's trust level, and returns 403 Forbidden if the actor's level is below the required minimum. A finer-grained capability check runs at the route handler level via `get_capabilities(actor_role)`, which returns an `ActorCapabilities` dataclass. Route handlers check the relevant capability inline.

---

## Scheduled Jobs

Three jobs run every 6 hours via APScheduler, registered in `xnch/main.py`:

| Job | Cron | Purpose |
|---|---|---|
| PatternExtractor | `hour="*/6"` | Queries episodes since last run, groups by (intent_class, action_type, entity_class, actor_role), computes Bayesian-smoothed confidence. |
| ScoreAdapter | `hour="*/6", minute=30` | Rolling 7-day vs 30-day accuracy per dimension. Drift > 0.05 triggers weight proposal. |
| PolicyCandidateGenerator | `hour="*/6", minute=45` | Reads low-success patterns, calls claude-judgment for policy DSL candidates, writes to policy_candidates table. |

One job runs daily via a Kubernetes CronJob:

| Job | Time | Purpose |
|---|---|---|
| Consolidation | 2 AM | Summarizes episodes, extracts graph triples, recomputes decay scores, archives stale episodes. |

---

## Attention Filter (Perception)

The perception subsystem applies four rules when processing sensory input:

1. Voice transcript + silence > 1.5 seconds → forward to gateway.
2. Screen pixel diff > 0.15 fraction → encode and store as episode.
3. File saved in vault → trigger file watcher.
4. Idle > 600 seconds → suppress responses, run consolidation.

---

## Audit System

Two audit mechanisms run in parallel:

**EventLog.** Append-only JSONL file at `~/.xnch/audit/events.jsonl`. Fire-and-forget emit. Fields: timestamp, level, component, event_type, message, data, trace_id.

**DecisionLedger.** SHA-256 chained, append-only, tamper-evident. Each entry hashes the previous entry's hash. A `verify_chain` static method validates the entire ledger's integrity.

**Langfuse observability.** The `LangfuseClient` uses HTTP Basic auth (public_key:secret_key) and logs LLM calls via `trace_llm_call` as generation events. Disabled when both key environment variables are empty.

---

## Hardware Assignment

| Node | Label | Services | Function |
|---|---|---|---|
| i7-node | `role=memory` | PostgreSQL 15 + pgvector, Redis, Langfuse, LiteLLM, xnch server, Perception daemonset | Stateful, data-heavy — stores all memory layers, manages governance and policy |
| i9-node | `role=inference` | vLLM + Gemma 4 26B, Nexi, mem0, Zep | Compute-heavy, GPU-dependent — runs LLM inference and all decision pipeline steps |

Both nodes are physical. vLLM + Gemma 4 26B runs on a single RTX 3090, achieving approximately 135 tokens per second. The perception daemonset on the i7-node manages a GTX 1650 for vision tasks (Moondream2) and runs Whisper for voice capture. The two nodes communicate over the Kubernetes cluster network — no external connectivity is required for inference operations.
