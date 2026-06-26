# EvaluatedPlan Schema

---
tags:
  - #reference
  - #contracts
  - #decision
---

Plan with evaluation scores.

## Definition

```python
class EvaluatedPlan:
    plan: Plan                       # The original plan
    scores: Dict[str, float]         # Dimension scores
    total_score: float              # Weighted total score
    evaluation_details: EvaluationDetails  # Detailed breakdown


class EvaluationDetails:
    policy_score: float            # Policy dimension score
    outcome_score: float           # Outcome dimension score
    risk_score: float              # Risk dimension score
    context_fit_score: float       # Context fit dimension score
    reasoning: Dict[str, str]      # Explanation per dimension
```

## JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["plan", "scores", "total_score"],
  "properties": {
    "plan": {
      "$ref": "plan.json"
    },
    "scores": {
      "type": "object",
      "properties": {
        "policy_score": {"type": "number"},
        "outcome_score": {"type": "number"},
        "risk_score": {"type": "number"},
        "context_fit_score": {"type": "number"}
      }
    },
    "total_score": {
      "type": "number",
      "minimum": 0.0,
      "maximum": 1.0
    },
    "evaluation_details": {
      "type": "object",
      "properties": {
        "reasoning": {
          "type": "object",
          "properties": {
            "policy": {"type": "string"},
            "outcome": {"type": "string"},
            "risk": {"type": "string"},
            "context_fit": {"type": "string"}
          }
        }
      }
    }
  }
}
```

## Example

```json
{
  "plan": {
    "plan_id": "plan_001",
    "steps": [...]
  },
  "scores": {
    "policy_score": 0.95,
    "outcome_score": 0.85,
    "risk_score": 0.90,
    "context_fit_score": 0.80
  },
  "total_score": 0.875,
  "evaluation_details": {
    "reasoning": {
      "policy": "No destructive operations detected",
      "outcome": "Optimal resource usage pattern",
      "risk": "No policy violations",
      "context_fit": "Matches recent successful backups"
    }
  }
}
```

## Evaluation Dimensions

| Dimension | Weight | Description |
|-----------|--------|-------------|
| Policy | 0.25 | Does the plan comply with active policies? |
| Outcome | 0.30 | How likely is a successful outcome? |
| Risk | 0.35 | What is the risk level of the action? |
| Context Fit | 0.10 | Does the action fit current constraints? |

## Score Calculation

```python
def calculate_total(scores, weights):
    return (
        scores['policy_score'] * weights['policy_score'] +
        scores['outcome_score'] * weights['outcome_score'] +
        scores['risk_score'] * weights['risk_score'] +
        scores['context_fit_score'] * weights['context_fit_score']
    )
```