# Learning Loop Component

---
tags:
  - #component
  - #learning
  - #memory
---

Enables xnch + Nexi to improve over time through structured outcome feedback — not model training. Composed of four sub-components that run after execution completes.

---

## Sub-Components

| Sub-Component | Trigger | Output |
|---------------|---------|--------|
| Outcome Collector | After every execution | Episode written to Episodic Store |
| Pattern Extractor | Every 6 hours (APScheduler) | Patterns written to Pattern Store |
| Score Adapter | When dimension accuracy < 0.6 | Updated weight config (versioned) |
| Policy Candidate Generator | After extraction, on low-success patterns | Policy candidates queued for review |

---

## Outcome Collector

Captures the execution result from xnch's outcome callback and writes an episode record.

```python
from xnch.learning import OutcomeCollector

collector = OutcomeCollector(episodic_store)

# Called by Nexi on POST /memory/write after execution completes
collector.record(
    decision_id="dec_abc123",
    intent_class="EXECUTION",
    action_type="DEPLOY",
    entity_class="ML_MODEL",
    outcome="SUCCESS",           # SUCCESS | PARTIAL | FAILURE
    prediction_delta=0.54        # abs(predicted_outcome_score - actual)
)
```

Episodes start `PENDING` when the decision is made and are completed by this call. A background reconciliation job flags stale `PENDING` episodes (no outcome received within TTL) for manual review.

---

## Pattern Extractor

Analyzes episodic data on a 6-hour schedule. Groups episodes by `(intent_class, action_type, entity_class, actor_role)` tuple. Requires a minimum of 10 observations before writing a pattern.

**Configuration:**
```yaml
learning:
  pattern_extractor:
    schedule: "0 */6 * * *"      # cron expression
    min_observations: 10
```

**Python API:**
```python
from xnch.learning import PatternExtractor

extractor = PatternExtractor(episodic_store, pattern_store)
extractor.run()                  # normally called by APScheduler
```

Patterns with `prediction_delta > 0.3` trigger an early extraction call — the extractor does not wait for the scheduled run when a decision significantly diverges from its predicted outcome.

---

## Score Adapter

Monitors per-dimension prediction accuracy. When accuracy (correlation between predicted score and actual outcome) for any dimension drops below 0.6, proposes a weight adjustment.

**Configuration:**
```yaml
learning:
  score_adapter:
    accuracy_threshold: 0.6
    adjustment_rate: 0.1
```

**Behavior:**
- Adjustments are not applied directly — they are submitted as `POLICY_CHECK` to xnch before activation
- Every weight change is versioned with the causative episode batch reference
- No automatic drift — all changes have an audit trail

```python
from xnch.learning import ScoreAdapter

adapter = ScoreAdapter(episodic_store, weight_config)
adapter.evaluate()               # checks all four dimensions
```

Evaluation dimensions: `policy_score`, `outcome_score`, `risk_score`, `context_fit_score`

---

## Policy Candidate Generator

When Pattern Extractor identifies patterns with `success_rate < 0.4` and `confidence > 0.6`, generates a soft policy candidate for operator review. Candidates are never applied automatically.

```python
from xnch.learning import PolicyCandidateGenerator

gen = PolicyCandidateGenerator(pattern_store, policy_candidates_store)
gen.run()
```

**Review via CLI:**
```bash
xnch learning review-candidates
```

Each candidate shows: the triggering pattern, observation count, success rate, and the proposed rule. Operators accept, reject, or modify before the rule enters the active policy set through xnch's normal policy deployment path.

---

## Data Flow

```
Execution Outcome (xnch callback)
        │
        ▼
  Outcome Collector ──▶ Episodic Store
                               │
                        every 6h or early trigger
                               ▼
                       Pattern Extractor ──▶ Pattern Store
                               │
                    accuracy < 0.6 per dimension
                               ▼
                        Score Adapter ──▶ Weight Config (versioned, xnch-gated)
                               │
                  success_rate < 0.4, confidence > 0.6
                               ▼
                  Policy Candidate Gen ──▶ Operator Review Queue
```

---

## Related

- [[architecture/_memory-map.md]]
- [[architecture/memory-system.md]]

## Monitoring

```yaml
metrics:
  learning:
    episodes_recorded_total: true
    patterns_extracted_total: true
    score_adaptations_total: true
    policy_candidates_generated_total: true
    dimension_accuracy:
      policy_score: true
      outcome_score: true
      risk_score: true
      context_fit_score: true
```
