# Scaling

---
tags:
  - #guide
  - #runtime
---

Horizontal scaling guide for xnch + Nexi.

## Architecture Options

### Single Node (Default)

All components on one machine:
- CLI connects to local API
- Local SQLite databases
- Local model inference

### Distributed

```
┌─────────────┐     ┌─────────────┐
│   CLI/API   │────▶│   Nexi      │
│   Node 1    │     │   Node 1    │
└─────────────┘     └─────────────┘
       │                   │
       │              ┌─────┴─────┐
       │              ▼           ▼
       │        ┌────────┐ ┌────────┐
       │        │ Memory │ │ Memory  │
       │        │ Node 1 │ │ Node 2  │
       │        └────────┘ └────────┘
       │
       ▼
┌─────────────┐
│   Model     │
│   (vLLM)    │
└─────────────┘
```

## Scaling Components

### API Scaling

```yaml
server:
  workers: 4  # Number of uvicorn workers
  
  # Or use external load balancer
  # nginx/haproxy in front of multiple instances
```

### Memory Scaling

#### Shared SQLite

Not recommended for >1 writer. Use instead:

**Option 1: PostgreSQL**

```yaml
memory:
  context_store:
    type: postgresql
    connection: postgresql://user:pass@host:5432/xnch
    
  outcome_store:
    type: postgresql
    connection: postgresql://user:pass@host:5432/xnch
```

**Option 2: Redis Cluster**

```yaml
memory:
  kv_cache:
    type: redis
    cluster:
      - host: node1:6379
      - host: node2:6379
      - host: node3:6379
```

#### Vector Store Scaling

sqlite-vec is embedded in SQLite and scales with the SQLite instance. For multi-writer scenarios, migrate the entire memory layer to PostgreSQL with pgvector:

```yaml
memory:
  vector_store:
    type: pgvector
    connection: postgresql://user:pass@host:5432/xnch
    embedding_dim: 384
```

### Model Scaling

**Option 1: Multiple vLLM Instances**

```yaml
model:
  provider: vllm
  endpoint: http://load-balancer:8000
  # Load balancer distributes requests
  
# vLLM behind nginx/haproxy
```

**Option 2: Model Router**

```yaml
model:
  provider: router
  
  routers:
    - name: fast
      endpoint: http://localhost:8000
      model: llama-3.1-8b
      
    - name: quality
      endpoint: http://remote:8000
      model: llama-3.1-70b
      
  # Route by intent complexity
  routing:
    - intent_complexity: low
      router: fast
    - intent_complexity: high
      router: quality
```

## Capacity Planning

### Metrics to Monitor

| Metric | Threshold | Action |
|--------|-----------|--------|
| API latency | >500ms | Scale API workers |
| Queue depth | >100 | Scale Nexi |
| Memory usage | >80% | Scale storage |
| Model latency | >2s | Add model instances |

### Scaling Triggers

```yaml
autoscale:
  enabled: true
  
  api:
    min_workers: 2
    max_workers: 8
    target_cpu: 70
    
  nexi:
    min_instances: 2
    max_instances: 8
    target_queue_depth: 50
```

## High Availability

### Multi-AZ Deployment

```
Region: us-east-1
├─ AZ1: API + Nexi + Memory Primary
├─ AZ2: API + Nexi + Memory Replica
└─ AZ3: API + Nexi + Memory Replica
```

### Failover

```yaml
ha:
  enabled: true
  
  memory:
    replication: async
    failover_timeout: 30s
    
  api:
    health_check_interval: 10s
    failover_threshold: 3
```

## Benchmarks

| Configuration | Throughput | Latency |
|---------------|------------|----------|
| Single node | 10 req/s | 200ms |
| 4 workers | 35 req/s | 180ms |
| Distributed (3 Nexi) | 80 req/s | 150ms |