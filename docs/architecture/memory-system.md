# Memory System

---
tags:
  - #architecture
  - #memory
  - #learning
  - #data
---

The memory system is not a log. It is a structured, queryable, evolving knowledge graph that reflects system state, prior decisions, outcomes, and learned policies. It feeds Nexi — not models directly.

---

## Key Principles

1. **Updated after execution, not after generation** — the system learns from what happened in the world, not from what the model said.
2. **Does not flow directly to models** — memory flows to Nexi, which decides what to surface, how to frame it, and what to withhold.
3. **Structured state, not context window** — typed entities with schema, not free-form blobs.
4. **Feedback loop is grounded** — `prediction_delta` measures accuracy against real outcomes.

---

## Stores

### Context Store

**Technology:** SQLite (WAL mode)

Typed entity storage. The authoritative record of governed memory. Every record carries: entity ID, timestamp, actor, action type, verdict, policy reference, and content hash.

Entity types: `Decision`, `Observation`, `Constraint`, `Relationship`

Key properties:
- WAL mode for concurrent reads without write-blocking
- JSON1 extension for semi-structured fields
- Schema-versioned via migrations
- Queryable by the Policy Engine at verdict time — "has this entity triggered this policy class N times in window W?" is a policy condition evaluated at request time

### Vector Index

**Technology:** sqlite-vec + sentence-transformers (all-MiniLM-L6-v2, 22MB, CPU)

Semantic retrieval for similar past decisions. Used when exact tuple matching on `(intent_class, action_type, entity_class, actor_role)` returns insufficient results. Embeddings are 384-dimensional, generated locally on CPU — no external model calls.

### KV Cache

**Technology:** Redis (Unix socket)

Session state and rate-limiting. Fast lookups for hot data with TTL-based expiry. Not used for persistent memory — only for in-flight session data and rate limit counters per actor.

### Episodic Store

**Technology:** SQLite

Records every decision with its outcome for the learning loop. Episodes start as `PENDING` and are completed via the execution outcome callback from xnch after real-world execution finishes.

Fields: `episode_id`, `intent_class`, `action_type`, `entity_class`, `outcome` (`SUCCESS | PARTIAL | FAILURE`), `prediction_delta`, `timestamp`

### Pattern Store

**Technology:** SQLite

Aggregated patterns derived from episodic history. Updated by the Pattern Extractor on a 6-hour schedule.

Fields: `context_signature` (hash of intent + context tuple), `success_rate`, `confidence`, `observation_count`, `avg_prediction_delta`

---

## Learning Layer

### Pattern Extractor

Runs every 6 hours via APScheduler. Groups episodes by `(intent_class, action_type, entity_class, actor_role)` tuple and computes `success_rate` and Bayesian-smoothed `confidence` per group. Minimum observation threshold: 10 episodes before a pattern is written.

### Score Adapter

Monitors dimension prediction accuracy. When accuracy for any evaluation dimension falls below 0.6 (correlation between predicted score and actual outcome), proposes a weight adjustment for that dimension. All adjustments are versioned, logged with the causative episode batch reference, and applied only after passing a `POLICY_CHECK` through xnch.

### Policy Candidate Generator

When Pattern Extractor identifies patterns with `success_rate < 0.4` and `confidence > 0.6`, generates soft policy candidates. Candidates require operator review before activation — they are not applied automatically.

---

## Data Flow

```
Intent
  └─▶ Context Store ──▶ Vector Index (semantic fallback)
         │
         ▼
   Execution Outcome
         │
         ▼
   Episodic Store ──▶ Pattern Extractor (6h) ──▶ Pattern Store
                                │
                                ▼
                         Score Adapter ──▶ Weight Config (versioned)
                                │
                                ▼
                       Policy Candidate Gen ──▶ Operator Review
```

---

## Memory Governance

All writes to the Context Store pass through xnch's `POST /memory/write` interface. Nexi never writes to memory directly. xnch validates write policy and schema before committing. This ensures memory integrity is enforced at the same chokepoint as all other governed actions.

All reads are governed via `POST /memory/read`. xnch applies read policy against actor capability scope before returning any content. Nexi cannot pull state it is not authorized to reason over.

---

## Schema reference

See [[schemas/episode.md]], [[schemas/pattern.md]], and [[schemas/intent.md]] for field-level specifications.

---

## Related

- [[_system-map.md]]
- [[_memory-map.md]]
