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
    safety_score: float             # Safety dimension score
    efficiency_score: float         # Efficiency dimension score
    compliance_score: float        # Compliance dimension score
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
        "safety": {"type": "number"},
        "efficiency": {"type": "number"},
        "compliance": {"type": "number"},
        "context_fit": {"type": "number"}
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
            "safety": {"type": "string"},
            "efficiency": {"type": "string"},
            "compliance": {"type": "string"},
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
    "safety": 0.95,
    "efficiency": 0.85,
    "compliance": 0.90,
    "context_fit": 0.80
  },
  "total_score": 0.875,
  "evaluation_details": {
    "reasoning": {
      "safety": "No destructive operations detected",
      "efficiency": "Optimal resource usage pattern",
      "compliance": "No policy violations",
      "context_fit": "Matches recent successful backups"
    }
  }
}
```

## Evaluation Dimensions

| Dimension | Weight | Description |
|-----------|--------|-------------|
| Safety | 0.30 | Does the plan cause harm? |
| Efficiency | 0.25 | Is resource usage optimal? |
| Compliance | 0.25 | Does it follow policies? |
| Context Fit | 0.20 | Does it match current context? |

## Score Calculation

```python
def calculate_total(scores, weights):
    return (
        scores['safety'] * weights['safety'] +
        scores['efficiency'] * weights['efficiency'] +
        scores['compliance'] * weights['compliance'] +
        scores['context_fit'] * weights['context_fit']
    )
```