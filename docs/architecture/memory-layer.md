# Memory Layer Architecture

Deep dive into the memory storage components.

## Overview

The Memory Layer provides structured storage for context, outcomes, and learned patterns. It consists of five stores using different technologies optimized for their specific use cases.

## Stores Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      Memory Layer                               │
├─────────────┬─────────────┬─────────────┬──────────┬───────────┤
│  Context    │   Vector    │    KV       │ Outcome  │  Pattern  │
│   Store     │   Index     │   Cache     │  Store   │   Store   │
├─────────────┼─────────────┼─────────────┼──────────┼───────────┤
│  SQLite     │  ChromaDB   │   Redis     │ SQLite   │  SQLite   │
│  (WAL)      │             │  (socket)   │          │           │
└─────────────┴─────────────┴─────────────┴──────────┴───────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  Episodic Store │
                    │    (SQLite)     │
                    └─────────────────┘
```

## Context Store

**Purpose**: Current execution context, schema, and working memory.

**Technology**: SQLite with WAL mode

**Schema**:
```sql
CREATE TABLE contexts (
    id TEXT PRIMARY KEY,
    intent_hash TEXT NOT NULL,
    intent_class TEXT NOT NULL,
    action_type TEXT NOT NULL,
    entity_class TEXT,
    parameters TEXT,  -- JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_intent_class ON contexts(intent_class);
CREATE INDEX idx_action_type ON contexts(action_type);
CREATE INDEX idx_created_at ON contexts(created_at);
```

**Operations**:
- `store(context)` - Write new context
- `retrieve(id)` - Get context by ID
- `recent(limit)` - Get recent contexts
- `search(intent_class, action_type)` - Find matching contexts

## Vector Index

**Purpose**: Semantic similarity search for context matching.

**Technology**: ChromaDB

**Configuration**:
```yaml
memory:
  vector_store:
    type: chroma
    path: ~/.xnch/memory/vectors
    collection: xnch_context
```

**Schema**:
- `context_id`: Reference to Context Store
- `embedding`: 384-dimension vector (configurable)
- `metadata`: intent_class, action_type, timestamp

**Operations**:
- `index(context)` - Add context to vector index
- `semantic_search(query, top_k)` - Find similar contexts
- `delete(context_id)` - Remove from index

## KV Cache

**Purpose**: Fast key-value lookups for frequently accessed data.

**Technology**: Redis (unix socket or TCP)

**Configuration**:
```yaml
memory:
  kv_cache:
    type: redis
    path: /var/run/redis/redis.sock
    # or TCP:
    # host: localhost
    # port: 6379
    ttl: 3600  # Default TTL in seconds
```

**Usage**:
- Cache LLM responses
- Store session state
- Quick lookups for pattern metadata

**Operations**:
- `set(key, value, ttl)` - Store with TTL
- `get(key)` - Retrieve
- `delete(key)` - Remove
- `exists(key)` - Check existence

## Outcome Store

**Purpose**: Historical execution outcomes for learning and analysis.

**Technology**: SQLite

**Schema**:
```sql
CREATE TABLE outcomes (
    id TEXT PRIMARY KEY,
    intent_hash TEXT NOT NULL,
    intent_class TEXT NOT NULL,
    action_type TEXT NOT NULL,
    entity_class TEXT,
    plan_id TEXT NOT NULL,
    status TEXT NOT NULL,  -- success, failure, partial
    result TEXT,  -- JSON result
    error TEXT,
    duration_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_intent_class ON outcomes(intent_class);
CREATE INDEX idx_status ON outcomes(status);
CREATE INDEX idx_created_at ON outcomes(created_at);
```

**Operations**:
- `store(outcome)` - Record execution result
- `recent(limit)` - Get recent outcomes
- `statistics(time_range)` - Get aggregate stats

## Pattern Store

**Purpose**: Learned patterns and heuristics extracted from outcomes.

**Technology**: SQLite

**Schema**:
```sql
CREATE TABLE patterns (
    id TEXT PRIMARY KEY,
    pattern_type TEXT NOT NULL,  -- sequence, frequency, correlation
    context_signature TEXT NOT NULL,  -- Hash of triggering context
    success_rate REAL NOT NULL,
    confidence REAL NOT NULL,
    observation_count INTEGER NOT NULL,
    extracted_from TEXT,  -- Reference to pattern extractor run
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_context_sig ON patterns(context_signature);
CREATE INDEX idx_success_rate ON patterns(success_rate);
```

**Operations**:
- `store(pattern)` - Save extracted pattern
- `lookup(context_signature)` - Find matching patterns
- `top_ranked(limit)` - Get highest confidence patterns

## Episodic Store

**Purpose**: Individual learning episodes for pattern extraction.

**Technology**: SQLite

**Schema**:
```sql
CREATE TABLE episodes (
    id TEXT PRIMARY KEY,
    intent_class TEXT NOT NULL,
    action_type TEXT NOT NULL,
    entity_class TEXT,
    outcome TEXT NOT NULL,  -- success, failure
    prediction_delta REAL NOT NULL,  -- Predicted vs actual
    context_snapshot TEXT,  -- JSON context at time of execution
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_intent_action ON episodes(intent_class, action_type);
CREATE INDEX idx_outcome ON episodes(outcome);
```

**Operations**:
- `record(episode)` - Add new episode
- `recent(limit)` - Get recent episodes
- `for_extraction(min_observations)` - Get data for pattern extractor

## Data Flow

```
Intent ──▶ Context Store ──▶ Vector Index
              │
              ▼
         Outcome Store ◀─── Execution
              │
              ▼
        Episodic Store
              │
              ▼
       Pattern Extractor
              │
              ▼
         Pattern Store
```

## Configuration Example

```yaml
memory:
  context_store:
    type: sqlite
    path: ~/.xnch/memory/context.db
    wal_mode: true
    
  vector_store:
    type: chroma
    path: ~/.xnch/memory/vectors
    collection: xnch_context
    embedding_model: all-MiniLM-L6-v2
    
  kv_cache:
    type: redis
    path: /var/run/redis/redis.sock
    ttl: 3600
    
  outcome_store:
    path: ~/.xnch/memory/outcomes.db
    
  pattern_store:
    path: ~/.xnch/memory/patterns.db
    
  episodic_store:
    path: ~/.xnch/memory/episodic.db
```