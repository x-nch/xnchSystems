# Memory Backend Configuration

Configure memory storage backends.

## Overview

The memory layer uses multiple backends:
- SQLite (Context, Outcome, Pattern, Episodic stores)
- ChromaDB (Vector Index)
- Redis (KV Cache)

## SQLite Configuration

```yaml
memory:
  context_store:
    type: sqlite
    path: ~/.xnch/memory/context.db
    wal_mode: true  # Recommended for concurrent access
    
  outcome_store:
    path: ~/.xnch/memory/outcomes.db
    
  pattern_store:
    path: ~/.xnch/memory/patterns.db
    
  episodic_store:
    path: ~/.xnch/memory/episodic.db
```

### Performance Tuning

```yaml
memory:
  context_store:
    type: sqlite
    path: ~/.xnch/memory/context.db
    wal_mode: true
    cache_size: 10000  # Page cache size
    journal_mode: wal   # Write-ahead logging
```

## ChromaDB Configuration

```yaml
memory:
  vector_store:
    type: chroma
    path: ~/.xnch/memory/vectors
    collection: xnch_context
    embedding_model: all-MiniLM-L6-v2  # Default
```

### Custom Embeddings

```yaml
memory:
  vector_store:
    type: chroma
    embedding_model: sentence-transformers/all-mpnet-base-v2
    embedding_dim: 768  # Match model dimension
```

## Redis Configuration

### Unix Socket (Recommended)

```yaml
memory:
  kv_cache:
    type: redis
    path: /var/run/redis/redis.sock
    ttl: 3600
```

### TCP Connection

```yaml
memory:
  kv_cache:
    type: redis
    host: localhost
    port: 6379
    db: 0
    ttl: 3600
```

### Redis Cluster

```yaml
memory:
  kv_cache:
    type: redis
    cluster:
      - host: node1, port: 6379
      - host: node2, port: 6379
      - host: node3, port: 6379
```

## Backend Comparison

| Backend | Use Case | Performance |
|---------|----------|-------------|
| SQLite | Context, Outcomes, Patterns | ~1ms read |
| ChromaDB | Semantic search | ~10ms query |
| Redis | Fast cache | ~0.1ms read |

## Disabling Backends

```yaml
memory:
  # Disable vector store
  vector_store:
    enabled: false
    
  # Disable Redis (use in-memory)
  kv_cache:
    enabled: false
```

## Monitoring

```bash
# Show memory stats
xnch memory stats
```