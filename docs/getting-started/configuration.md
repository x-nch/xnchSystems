# Configuration

Comprehensive configuration guide for xnch + Nexi.

## Configuration Files

### Main Config Location

- Default: `~/.xnch/config.yaml`
- Custom: `XNCH_CONFIG=/path/to/config.yaml`

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `XNCH_CONFIG` | Config file path | `~/.xnch/config.yaml` |
| `XNCH_DATA_DIR` | Data directory | `~/.xnch` |
| `XNCH_LOG_LEVEL` | Log level | `INFO` |

## Configuration Sections

### Model Configuration

```yaml
model:
  provider: vllm  # vllm, ollama, openai, anthropic
  endpoint: http://localhost:8000
  model_name: llama-3.1-8b
  temperature: 0.7
  max_tokens: 2048
```

### Memory Configuration

```yaml
memory:
  context_store:
    type: sqlite
    path: ~/.xnch/memory/context.db
    
  vector_store:
    type: chroma
    path: ~/.xnch/memory/vectors
    
  kv_cache:
    type: redis
    path: /var/run/redis/redis.sock
    # or for TCP:
    # host: localhost
    # port: 6379
    
  outcome_store:
    path: ~/.xnch/memory/outcomes
    
  pattern_store:
    path: ~/.xnch/memory/patterns
```

### Audit Configuration

```yaml
audit:
  event_log:
    path: ~/.xnch/audit/events.jsonl
    
  decision_ledger:
    path: ~/.xnch/audit/decisions.jsonl
    
  replay_enabled: true
```

### Learning Configuration

```yaml
learning:
  enabled: true
  pattern_extractor:
    schedule: "0 */6 * *"  # Every 6 hours
  score_adapter:
    accuracy_threshold: 0.6
```

## Full Configuration Example

```yaml
xnch:
  version: "1.0.0"
  
model:
  provider: vllm
  endpoint: http://localhost:8000
  model_name: llama-3.1-8b
  temperature: 0.7
  max_tokens: 2048
  timeout: 120

memory:
  context_store:
    type: sqlite
    path: ~/.xnch/memory/context.db
    wal_mode: true
    
  vector_store:
    type: chroma
    path: ~/.xnch/memory/vectors
    collection: xnch_context
    
  kv_cache:
    type: redis
    path: /var/run/redis/redis.sock
    ttl: 3600
    
  outcome_store:
    path: ~/.xnch/memory/outcomes
    
  pattern_store:
    path: ~/.xnch/memory/patterns

audit:
  event_log:
    path: ~/.xnch/audit/events.jsonl
    rotation: daily
    retention: 30
    
  decision_ledger:
    path: ~/.xnch/audit/decisions.jsonl
    chain_hash: sha256
    
  replay_enabled: true

learning:
  enabled: true
  episodic_store:
    path: ~/.xnch/memory/episodic.db
    
  pattern_extractor:
    schedule: "0 */6 * *"
    min_observations: 10
    
  score_adapter:
    accuracy_threshold: 0.6
    adjustment_rate: 0.1

nexi:
  max_candidates: 5
  evaluation_dimensions:
    - safety
    - efficiency
    - compliance
    - context_fit
    
  policy_paths:
    - ~/.xnch/policies/default.yaml
    - ~/.xnch/policies/custom.yaml
```

## Validation

```bash
xnch config validate
```

Validates:
- YAML syntax
- Required fields
- File/directory paths
- Connection strings