# Audit Component

---
tags:
  - #component
  - #policy
  - #execution
---

Provides a complete, cryptographically verifiable decision trail for every action evaluated by xnch. Composed of three sub-components: Event Log, Decision Ledger, and Replay Engine.

---

## Related

- [[architecture/_system-map.md]]
- [[_memory-map.md]]

---

| Sub-Component | File | Purpose |
|---------------|------|---------|
| Event Log | `~/.xnch/audit/events.jsonl` | Append-only operational log |
| Decision Ledger | `~/.xnch/audit/decisions.jsonl` | SHA-256 chained decision record |
| Replay Engine | `replay.py` | Decision replay and chain verification |

---

## Event Log

Append-only log of all system events. Written by every component using structured logging.

**Configuration:**
```yaml
audit:
  event_log:
    path: ~/.xnch/audit/events.jsonl
    rotation: daily        # daily | weekly | size
    retention: 30          # days
```

**Event schema:**
```json
{
  "timestamp": "2026-04-18T10:30:00.000Z",
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

**Event types by component:**

| Component | Events |
|-----------|--------|
| Intent Parser | `input_received`, `intent_parsed` |
| Nexi Engine | `options_generated`, `candidates_filtered`, `evaluation_complete`, `decision_made` |
| Model Adapter | `request_sent`, `response_received`, `error` |
| Memory | `context_stored`, `outcome_recorded`, `pattern_extracted` |
| Execution | `plan_started`, `step_completed`, `plan_finished` |
| Learning | `episode_recorded`, `score_adjusted` |

---

## Decision Ledger

Cryptographically chained record of every decision submitted to xnch. Each entry links to its predecessor via SHA-256 hash. Any tampering breaks the chain.

**Configuration:**
```yaml
audit:
  decision_ledger:
    path: ~/.xnch/audit/decisions.jsonl
    chain_hash: sha256
    retention: 365         # days
```

**Entry schema:**
```json
{
  "decision_id": "dec_abc123",
  "timestamp": "2026-04-18T10:30:00.000Z",
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

**Chain verification:**
```python
def verify_chain(ledger_path: str) -> bool:
    with open(ledger_path) as f:
        prev_entry = None
        for line in f:
            entry = json.loads(line)
            if prev_entry:
                assert entry["prev_hash"] == prev_entry["hash"]
                content = json.dumps(
                    {k: v for k, v in entry.items() if k != "hash"},
                    sort_keys=True
                )
                expected = f"sha256:{hashlib.sha256(content.encode()).hexdigest()}"
                assert entry["hash"] == expected
            prev_entry = entry
    return True
```

---

## Replay Engine

Replays past decisions for debugging, what-if analysis, and audit verification.

**Configuration:**
```yaml
audit:
  replay_enabled: true
```

**CLI usage:**
```bash
# Replay a decision
xnch replay dec_abc123

# Replay with alternate policies
xnch replay dec_abc123 --policies=./alternate.yaml

# Verify ledger integrity
xnch audit verify
```

**Python API:**
```python
from xnch.audit import ReplayEngine

engine = ReplayEngine()

result = engine.replay(
    decision_id="dec_abc123",
    policy_overrides=PolicySet(...)   # optional
)

is_valid = engine.verify_chain()
```

---

## Storage Management

**Log rotation:**

| Strategy | Behavior |
|----------|----------|
| `daily` | New file at midnight |
| `weekly` | New file Monday |
| `size` | New file at size threshold |

**Manual cleanup:**
```bash
xnch audit cleanup --older-than=30d
```

---

## Security Properties

- Files opened in append mode only — no update or delete path exists
- SHA-256 chain prevents silent modification of historical records
- Recommended file permissions: `600` (owner read/write only)
- Audit emission is synchronous with xnch verdict issuance — the log is consistent with the verdict stream by design

---

## Monitoring

```yaml
metrics:
  audit:
    decisions_per_hour: true
    ledger_growth_rate: true
    replay_requests: true
```
