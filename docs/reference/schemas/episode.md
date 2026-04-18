# Episode Schema

Learning episode record.

## Definition

```python
class Episode:
    id: str                        # Unique episode identifier
    intent_class: str              # Intent class
    action_type: str              # Action type
    entity_class: Optional[str]   # Entity class
    outcome: str                  # success or failure
    prediction_delta: float       # Prediction error (predicted - actual)
    context_snapshot: Dict[str, Any]  # Context at execution time
    created_at: datetime          # Episode creation time
```

## JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["id", "intent_class", "action_type", "outcome", "prediction_delta"],
  "properties": {
    "id": {
      "type": "string"
    },
    "intent_class": {
      "type": "string"
    },
    "action_type": {
      "type": "string"
    },
    "entity_class": {
      "type": "string"
    },
    "outcome": {
      "type": "string",
      "enum": ["success", "failure"]
    },
    "prediction_delta": {
      "type": "number",
      "description": "Predicted score minus actual (negative = improvement)"
    },
    "context_snapshot": {
      "type": "object"
    },
    "created_at": {
      "type": "string",
      "format": "date-time"
    }
  }
}
```

## Example

```json
{
  "id": "ep_abc123",
  "intent_class": "execute",
  "action_type": "backup",
  "entity_class": "database",
  "outcome": "success",
  "prediction_delta": -0.1,
  "context_snapshot": {
    "time_of_day": "02:00",
    "day_of_week": "Monday",
    "system_load": "low",
    "recent_failures": 0
  },
  "created_at": "2024-01-15T02:30:00.000Z"
}
```

## Prediction Delta

The `prediction_delta` field represents how wrong the system's prediction was:

| Value | Meaning |
|-------|---------|
| Negative | Prediction was too pessimistic (actual better than predicted) |
| Zero | Prediction was accurate |
| Positive | Prediction was too optimistic (actual worse than predicted) |

This is used by the Score Adapter to adjust evaluation weights when predictions are consistently off.