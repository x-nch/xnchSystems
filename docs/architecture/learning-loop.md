# Learning System Architecture

Deep dive into the continuous learning components.

## Overview

The Learning Loop enables xnch + Nexi to improve over time by collecting outcomes, extracting patterns, adapting scores, and generating policy candidates.

## Components

```
┌─────────────────────────────────────────────────────────────────┐
│                     Learning Loop                               │
├─────────────────┬─────────────────┬─────────────────────────────┤
│   Outcome       │    Pattern      │        Score               │
│   Collector     │   Extractor     │       Adapter              │
├─────────────────┼─────────────────┼─────────────────────────────┤
│                 │    (6h schedule)│  (accuracy < 0.6 trigger)   │
└─────────────────┴─────────────────┴─────────────────────────────┘
                              │
                              ▼
              ┌───────────────────────────────┐
              │    Policy Candidate Gen       │
              └───────────────────────────────┘
```

## Episodic Store

**Purpose**: Records individual learning episodes - the raw data for learning.

**Schema**:
```sql
CREATE TABLE episodes (
    id TEXT PRIMARY KEY,
    intent_class TEXT NOT NULL,
    action_type TEXT NOT NULL,
    entity_class TEXT,
    outcome TEXT NOT NULL,  -- success, failure
    prediction_delta REAL NOT NULL,  -- Predicted vs actual (negative = improvement)
    context_snapshot TEXT,  -- JSON context at execution time
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_intent_action ON episodes(intent_class, action_type);
CREATE INDEX idx_outcome ON episodes(outcome);
CREATE INDEX idx_created_at ON episodes(created_at);
```

**Episode Record**:
```python
class Episode:
    intent_class: str      # e.g., "execute", "query"
    action_type: str       # e.g., "run_command", "read_file"
    entity_class: str      # e.g., "file", "service"
    outcome: str          # "success" or "failure"
    prediction_delta: float # How off was the prediction?
                           # Positive = worse than expected
                           # Negative = better than expected
    context_snapshot: Dict  # Context at execution time
```

## Outcome Collector

**Purpose**: Captures execution results and converts them to episodes for the episodic store.

**Trigger**: After every plan execution (Step 10 of data flow)

**Logic**:
```python
def collect_outcome(execution_result, plan, intent):
    # Determine outcome
    if execution_result.status == "success":
        outcome = "success"
    elif execution_result.status == "failure":
        outcome = "failure"
    else:
        outcome = "partial"
    
    # Calculate prediction delta
    # Compare predicted outcome with actual
    predicted_safety = plan.scores.safety
    actual_safety = calculate_actual_safety(execution_result)
    prediction_delta = predicted_safety - actual_safety
    
    # Create episode
    episode = Episode(
        intent_class=intent.intent_class,
        action_type=intent.action_type,
        entity_class=intent.entity_class,
        outcome=outcome,
        prediction_delta=prediction_delta,
        context_snapshot=get_current_context()
    )
    
    episodic_store.store(episode)
```

## Pattern Extractor

**Purpose**: Analyzes episodic data to extract reusable patterns. Runs on a schedule.

**Schedule**: Every 6 hours (configurable)

**Configuration**:
```yaml
learning:
  pattern_extractor:
    schedule: "0 */6 * *"  # Cron expression
    min_observations: 10  # Minimum episodes to extract pattern
```

### Extraction Logic

**Pattern Types**:

1. **Sequence Patterns**: Common action sequences for intent classes
2. **Frequency Patterns**: Action types that commonly succeed/fail for entity classes
3. **Correlation Patterns**: Context conditions that correlate with outcomes

```python
def extract_patterns():
    # Get episodes since last run
    episodes = episodic_store.get_since(last_run_time)
    
    # Group by intent_class + action_type
    for (intent_class, action_type), group in episodes.groupby(['intent_class', 'action_type']):
        if len(group) < min_observations:
            continue
            
        # Calculate success rate
        success_count = (group.outcome == 'success').sum()
        success_rate = success_count / len(group)
        
        # Calculate confidence (Bayesian smoothing)
        confidence = (success_count + 1) / (len(group) + 2)
        
        # Extract context signature
        context_sig = extract_context_signature(group)
        
        # Create pattern
        pattern = Pattern(
            pattern_type="frequency",
            context_signature=context_sig,
            success_rate=success_rate,
            confidence=confidence,
            observation_count=len(group)
        )
        
        pattern_store.store(pattern)
```

**Context Signature**:
```python
def extract_context_signature(episodes):
    """Create a hash representing the typical context for this pattern."""
    features = {
        'intent_class': mode(episodes.intent_class),
        'action_type': mode(episodes.action_type),
        'hour_of_day': mode(episodes.context_snapshot.hour),
    }
    return hash(features)
```

## Score Adapter

**Purpose**: Adjusts evaluation weights when dimension prediction accuracy falls below threshold.

**Trigger**: When dimension accuracy < 0.6

**Configuration**:
```yaml
learning:
  score_adapter:
    accuracy_threshold: 0.6
    adjustment_rate: 0.1
```

### Adaptation Logic

```python
def adapt_scores():
    for dimension in ['safety', 'efficiency', 'compliance', 'context_fit']:
        # Get episodes that used this dimension
        episodes = episodic_store.get_by_dimension(dimension)
        
        if len(episodes) < 10:
            continue
            
        # Calculate prediction accuracy
        # For each episode, compare predicted score to actual outcome
        predictions = [e.predicted_scores[dimension] for e in episodes]
        actuals = [1.0 if e.outcome == 'success' else 0.0 for e in episodes]
        
        accuracy = correlation(predictions, actuals)
        
        if accuracy < accuracy_threshold:
            # Adjust weight
            current_weight = evaluation_weights[dimension]
            
            # If predictions too optimistic, reduce weight
            if accuracy < 0:
                new_weight = current_weight * (1 - adjustment_rate)
            # If predictions too pessimistic, increase weight
            else:
                new_weight = current_weight * (1 + adjustment_rate)
            
            evaluation_weights[dimension] = new_weight
            
            # Log adaptation
            logger.info(f"Adapted {dimension} weight: {current_weight} -> {new_weight}")
```

## Policy Candidate Generation

**Purpose**: Suggests new policy rules based on observed failure patterns.

**Trigger**: After pattern extraction when high-failure patterns detected

```python
def generate_policy_candidates():
    # Find patterns with low success rates
    low_success_patterns = pattern_store.find(success_rate < 0.4)
    
    for pattern in low_success_patterns:
        # Generate policy candidate
        candidate = PolicyCandidate(
            description=f"Prevent {pattern.action_type} on {pattern.context_signature}",
            rule={
                'intent_class': pattern.intent_class,
                'action_type': pattern.action_type,
                'context': pattern.context_signature
            },
            confidence=pattern.confidence,
            based_on_observations=pattern.observation_count
        )
        
        # Store for review
        policy_candidates_store.store(candidate)
        
# Reviewed in admin UI or via CLI
# xnch learning review-candidates
```

## Data Flow

```
Execution Result
       │
       ▼
┌─────────────────┐
│Outcome Collector│ ──▶ Episodic Store
└─────────────────┘
       │
       ▼ (every 6h)
┌─────────────────┐
│Pattern Extractor│ ──▶ Pattern Store
└─────────────────┘
       │
       ▼ (accuracy < 0.6)
┌─────────────────┐
│  Score Adapter  │ ──▶ Evaluation Weights
└─────────────────┘
       │
       ▼ (low success patterns)
┌─────────────────────┐
│ Policy Candidate Gen│ ──▶ Policy Candidates
└─────────────────────┘
```

## Monitoring

```yaml
# Learning metrics
metrics:
  learning:
    episodes_recorded_total: true
    patterns_extracted_total: true
    score_adaptations_total: true
    policy_candidates_generated_total: true
    
    # Per-dimension accuracy
    dimension_accuracy:
      safety: true
      efficiency: true
      compliance: true
      context_fit: true
```