# Troubleshooting

---
tags:
  - #guide
  - #reference
---

Common issues and solutions.

## Quick Diagnostics

```bash
# Run system check
xnch doctor

# Check component status
xnch health
```

## Common Issues

### CLI Issues

#### Command Not Found

**Symptom**: `xnch: command not found`

**Solution**:
```bash
# Install CLI
pip install xnch-cli

# Or add to PATH
export PATH="$PATH:$HOME/.local/bin"
```

#### Config Not Found

**Symptom**: `Config file not found`

**Solution**:
```bash
# Initialize config
xnch init

# Or specify config
xnch --config /path/to/config.yaml execute "..."
```

### Execution Issues

#### No Valid Candidates

**Symptom**: `No valid candidates found after policy filtering`

**Cause**: All candidates violated at least one policy

**Solution**:
```bash
# Check policies
xnch policy list

# Test with relaxed policies
xnch execute "..." --dry-run --show-candidates
```

#### Model Timeout

**Symptom**: `Model request timeout`

**Solution**:
```yaml
# Increase timeout in config
model:
  timeout: 300  # 5 minutes
```

#### Execution Failure

**Symptom**: `Execution failed: command exited with code 1`

**Debug**:
```bash
# Run with verbose output
xnch execute "..." --verbose

# Check audit logs
xnch audit events --level=ERROR --since=1h
```

### Memory Issues

#### SQLite Lock Error

**Symptom**: `database is locked`

**Solution**:
```yaml
# Enable WAL mode
memory:
  context_store:
    wal_mode: true
```

#### Redis Connection Failed

**Symptom**: `Could not connect to Redis`

**Solution**:
```bash
# Check Redis is running
redis-cli ping

# Or disable Redis
memory:
  kv_cache:
    enabled: false
```

#### Vector Index Error

**Symptom**: `sqlite-vec: vector table not found` or `no such table: vec_contexts`

**Solution**:
```bash
# Recreate vector index
xnch memory clear --store=vector
```

### Model Issues

#### vLLM Connection Refused

**Symptom**: `Connection refused to vLLM endpoint`

**Solution**:
```bash
# Check vLLM is running
curl http://localhost:8000/v1/models

# Start vLLM
vllm serve llama-3.1-8b-instruct
```

#### Model Not Found

**Symptom**: `Model not found: llama-3.1-8b`

**Solution**:
```bash
# Pull model
ollama pull llama3

# Or check model name
ollama list
```

### Learning Issues

#### Pattern Extraction Failed

**Symptom**: `Pattern extraction failed: insufficient data`

**Solution**:
- Wait for more episodes to accumulate
- Lower minimum observations:
```yaml
learning:
  pattern_extractor:
    min_observations: 5
```

#### Score Adaptation Not Triggering

**Symptom**: `Scores not adapting`

**Solution**:
- Check sufficient episodes exist
- Verify accuracy threshold:
```yaml
learning:
  score_adapter:
    accuracy_threshold: 0.6
```

## Debug Mode

Enable detailed logging:

```bash
# Set log level
export XNCH_LOG_LEVEL=DEBUG

# Run command
xnch execute "..." --verbose
```

## Getting Help

```bash
# Show system info
xnch doctor --verbose

# Export diagnostics
xnch doctor --export=diagnostics.json
```