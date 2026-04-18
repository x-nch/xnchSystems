# Audit Layer Architecture

Deep dive into the audit and logging components.

## Overview

The Audit Layer provides complete decision trail with cryptographic verification. It consists of three main components: Event Log, Decision Ledger, and Replay Engine.

## Components

```
┌─────────────────────────────────────────────────────────────────┐
│                       Audit Layer                               │
├─────────────────┬─────────────────────┬─────────────────────────┤
│   Event Log    │  Decision Ledger    │    Replay Engine        │
│  (Append-only) │  (JSONL + SHA256)   │                         │
├─────────────────┼─────────────────────┼─────────────────────────┤
│  events.jsonl  │ decisions.jsonl     │  replay.py              │
│                │                     │                         │
└─────────────────┴─────────────────────┴─────────────────────────┘
```

## Event Log

**Purpose**: Append-only log of all system events for debugging and analysis.

**Format**: JSON Lines (JSONL)

**Configuration**:
```yaml
audit:
  event_log:
    path: ~/.xnch/audit/events.jsonl
    rotation: daily      # daily, weekly, size
    retention: 30        # days to keep
```

**Event Schema**:
```json
{
  "timestamp": "2024-01-15T10:30:00.000Z",
  "level": "INFO",
  "component": "nexi.evaluator",
  "event_type": "evaluation_complete",
  "message": "Evaluated 5 candidates",
  "data": {
    "candidate_count": 5,
    "duration_ms": 234
  },
  "trace_id": "abc123-def456"
}
```

**Log Levels**:
- `DEBUG`: Detailed debugging information
- `INFO`: Normal operation events
- `WARNING`: Potential issues
- `ERROR`: Errors that were handled
- `CRITICAL`: Unhandled critical errors

**Event Types by Component**:

| Component | Events |
|-----------|--------|
| Intent Parser | input_received, intent_parsed |
| Nexi Engine | options_generated, candidates_filtered, evaluation_complete, decision_made |
| Model Adapter | request_sent, response_received, error |
| Memory Layer | context_stored, outcome_recorded, pattern_extracted |
| Execution | plan_started, step_completed, plan_finished |
| Learning | episode_recorded, score_adjusted |

## Decision Ledger

**Purpose**: Cryptographically verifiable record of all decisions made by Nexi.

**Format**: JSON Lines with SHA-256 chain

**Configuration**:
```yaml
audit:
  decision_ledger:
    path: ~/.xnch/audit/decisions.jsonl
    chain_hash: sha256
```

**Entry Schema**:
```json
{
  "decision_id": "dec_abc123",
  "timestamp": "2024-01-15T10:30:00.000Z",
  "intent_hash": "sha256:xyz789",
  "candidates_count": 5,
  "selected_plan": {
    "plan_id": "plan_001",
    "score": 0.87,
    "dimension_scores": {
      "safety": 0.95,
      "efficiency": 0.82,
      "compliance": 0.90,
      "context_fit": 0.78
    }
  },
  "decision_token": "tok_xyz789",
  "hash": "sha256:abc123",
  "prev_hash": "sha256:def456"
}
```

**Chain Verification**:
```python
def verify_chain(ledger_path):
    with open(ledger_path, 'r') as f:
        prev_entry = None
        for line in f:
            entry = json.loads(line)
            
            if prev_entry:
                # Verify chain linkage
                assert entry['prev_hash'] == prev_entry['hash']
                
                # Verify hash integrity
                content_to_hash = json.dumps({
                    k: v for k, v in entry.items() 
                    if k != 'hash'
                }, sort_keys=True)
                expected_hash = f"sha256:{hashlib.sha256(content_to_hash).hexdigest()}"
                assert entry['hash'] == expected_hash
                
            prev_entry = entry
```

## Replay Engine

**Purpose**: Ability to replay past decisions for debugging, auditing, and what-if analysis.

**Capabilities**:
1. **Decision Replay**: Re-run decision logic for a past decision
2. **What-If Analysis**: Test different policy configurations against historical decisions
3. **Audit Verification**: Verify integrity of decision chain

**Configuration**:
```yaml
audit:
  replay_enabled: true
```

**Usage**:

```bash
# Replay a specific decision
xnch replay dec_abc123

# Replay with modified policies
xnch replay dec_abc123 --policies=./new_policies.yaml

# Verify ledger integrity
xnch audit verify
```

**Replay API**:
```python
from xnch.audit import ReplayEngine

engine = ReplayEngine()

# Replay a specific decision
result = engine.replay(
    decision_id="dec_abc123",
    # Optional: override policies
    policy_overrides=PolicySet(...)
)

# Verify ledger integrity
is_valid = engine.verify_chain()
```

## Storage Management

### Rotation

| Strategy | Description |
|----------|-------------|
| `daily` | New file each day at midnight |
| `weekly` | New file each week on Monday |
| `size` | New file when current exceeds size limit |

### Retention

```yaml
audit:
  event_log:
    retention: 30  # Keep 30 days
    
  decision_ledger:
    retention: 365  # Keep 1 year
```

### Cleanup

```bash
# Manual cleanup
xnch audit cleanup --older-than=30d
```

## Security Considerations

1. **Append-Only**: Files are opened in append mode only
2. **Immutability**: No update or delete operations on historical records
3. **Chain Integrity**: SHA-256 chain prevents tampering
4. **Access Control**: Recommended file permissions `600` (owner only)

## Monitoring

```yaml
# Prometheus metrics
metrics:
  enabled: true
  port: 9090
  
  # Audit-specific metrics
  audit:
    decisions_per_hour: true
    ledger_growth_rate: true
    replay_requests: true
```