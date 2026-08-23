# Data Model

Audience: devs. Sources: `xnch/memory/pg_episodic_store.py`,
`relationship_store.py`, `quarantine_store.py`, `pattern_store.py`,
`graph_store.py`, `goal_store.py`, `workflow_store.py`; diagram suite §6
(authoritative ERDs reproduced here).

Eight-plus tables across Postgres, Kuzu, SQLite, Redis.

## Postgres — episodic core (pgvector)

```mermaid
erDiagram
  episodes {
    uuid id PK
    text type
    text raw_text
    text summary
    vector384 embedding
    float importance
    int recall_count
    timestamptz last_recalled
    float decay_score
    boolean archived
    timestamptz timestamp
    timestamptz created_at
    uuid session_id "nullable; pre-migration rows NULL"
  }
  decision_episodes {
    uuid episode_id PK
    text decision_id
    text intent_class
    text action_type
    text entity_class
    text actor_role
    text outcome
    float prediction_delta
    boolean early_reextraction_flag
    jsonb context_snapshot
    jsonb scores_json
    text generation_path
    timestamptz created_at
    timestamptz completed_at
  }
  patterns {
    uuid pattern_id PK
    text context_signature UK
    text intent_class
    text action_type
    text entity_class
    text actor_role
    float success_rate
    float confidence
    int observation_count
    float avg_prediction_delta
    text extraction_run_id
    timestamptz created_at
    timestamptz updated_at
  }
  episodes ||--o| decision_episodes : decision_id
  decision_episodes }o--|| patterns : tuple_agg
```

## Postgres — relationships & quarantine

```mermaid
erDiagram
  relationship_memory {
    uuid id PK
    text entity_a_id
    text entity_b_id
    text relationship_type
    float strength
    text_array evidence
    timestamptz first_seen
    timestamptz last_reinforced
    int reinforcement_count
  }
  quarantine_memories {
    uuid id PK
    text memory_type
    text raw_text
    text summary
    float importance
    text quarantine_reason
    text quarantined_by
    text original_actor_role
    text original_trust_level
    timestamptz created_at
    timestamptz released_at
    text released_by
  }
```

## Kuzu — semantic graph

File: `~/.xnch/graph.kuzu`. `entities(entity_id PK, name, type, created_at)`
connected by typed `relations(rel_type, confidence, created_at)`.
Written by consolidation's graph extractor; read by chat assembly for entity
context.

## SQLite — governance stores

| DB/file | Tables | Owner |
|---|---|---|
| `~/.xnch/data/episodic.db` | sqlite_episodes (verdict-path mirror incl. schema_version) | EpisodicStore |
| pattern store (SQLite) | patterns cache | PatternStore |
| goal store (SQLite) | goals + leases (`claim_next_goal`) | GoalStore |
| workflow store (SQLite) | workflows, steps (status/lease_owner/lease_expires_at/payload_json/max_retries), runs, approvals (producer_type/producer_id/status/snapshot_json) | WorkflowStore |

Workflow step states: see [workflows & HITL](workflows-hitl.md).

## Redis keyspace

L0 sensory entries (~60 s TTL), L1 working-memory sessions×turns, KV cache,
session dedup, rate limiting, intent recall cache.

## Cross-store links

Consolidation flows episodes → relationship_memory → mirrored into Kuzu;
the verdict path mirrors decision tuples into SQLite while PG holds the
canonical decision_episodes row.
