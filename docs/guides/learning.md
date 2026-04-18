# Understanding Learning

---
tags:
  - #guide
  - #learning
---

How the learning system improves over time.

## Overview

The Learning Loop enables xnch + Nexi to learn from past executions and improve decision quality. It consists of:
- Outcome Collection
- Pattern Extraction
- Score Adaptation
- Policy Candidate Generation

## The Learning Cycle

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Execute    │────▶│   Collect    │────▶│   Extract    │
│    Plan      │     │   Outcome    │     │   Patterns   │
└──────────────┘     └──────────────┘     └──────────────┘
                                                 │
                                                 ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Adapt      │◀────│   Generate   │◀────│   Review     │
│   Scores     │     │  Candidates  │     │  Patterns    │
└──────────────┘     └──────────────┘     └──────────────┘
```

## Learning Data Flow

### 1. Outcome Collection

Every execution generates an episode:

```python
episode = Episode(
    intent_class="execute",
    action_type="backup",
    entity_class="database",
    outcome="success",  # or "failure"
    prediction_delta=-0.1,  # Predicted 0.9, got 0.8
    context_snapshot={...}
)
```

### 2. Pattern Extraction (Every 6 hours)

Analyzes episodes to find patterns:

```python
# Example extracted pattern
Pattern(
    context_signature="execute+backup+database",
    success_rate=0.85,
    confidence=0.9,
    observation_count=100
)
```

### 3. Score Adaptation (When accuracy < 0.6)

Adjusts evaluation weights:

```python
# If safety predictions are wrong >40% of the time
# Reduce safety weight, increase other weights
evaluation_weights.safety = 0.30 -> 0.25
evaluation_weights.efficiency = 0.25 -> 0.28
```

### 4. Policy Candidate Generation

Suggests new policies from failure patterns:

```python
# High failure pattern detected
PolicyCandidate(
    description="Prevent backup on Fridays",
    rule={"action_type": "backup", "day_of_week": "Friday"},
    confidence=0.8
)
```

## What Gets Learned

### From Successes

- Which action sequences work well
- Optimal context conditions
- Reliable patterns

### From Failures

- Risky action combinations
- Context conditions to avoid
- Policy gaps

## Monitoring Learning

```bash
# View learning statistics
xnch learning stats

# Show recent patterns
xnch learning patterns

# Show policy candidates
xnch learning candidates
```

### Key Metrics

| Metric | Description |
|--------|-------------|
| Episodes recorded | Total learning episodes |
| Patterns extracted | Number of patterns discovered |
| Success rate | Overall execution success rate |
| Dimension accuracy | How accurate each dimension's predictions are |

## What's NOT Learned

- **User intent**: Intent classification is fixed
- **Security policies**: Security policies are never auto-generated
- **Credentials**: No sensitive data is ever learned or stored

## Privacy

All learning happens locally:
- No data leaves your infrastructure
- Patterns are based on your execution history
- Can be disabled in config:

```yaml
learning:
  enabled: false
```