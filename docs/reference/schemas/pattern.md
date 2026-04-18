# Pattern Schema

---
tags:
  - #reference
  - #contracts
  - #learning
---

Extracted learning pattern.

## Definition

```python
class Pattern:
    id: str                        # Unique pattern identifier
    pattern_type: str              # sequence, frequency, correlation
    context_signature: str         # Hash of triggering context
    success_rate: float            # Historical success rate (0.0-1.0)
    confidence: float              # Pattern confidence (0.0-1.0)
    observation_count: int         # Number of observations
    extracted_from: str            # Reference to extraction run
    metadata: Dict[str, Any]       # Additional metadata
    created_at: datetime          # Pattern creation time
    updated_at: datetime          # Last update time
```

## JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["id", "pattern_type", "context_signature", "success_rate", "confidence"],
  "properties": {
    "id": {
      "type": "string"
    },
    "pattern_type": {
      "type": "string",
      "enum": ["sequence", "frequency", "correlation"]
    },
    "context_signature": {
      "type": "string",
      "description": "Hash of triggering context"
    },
    "success_rate": {
      "type": "number",
      "minimum": 0.0,
      "maximum": 1.0
    },
    "confidence": {
      "type": "number",
      "minimum": 0.0,
      "maximum": 1.0
    },
    "observation_count": {
      "type": "integer",
      "minimum": 0
    },
    "extracted_from": {
      "type": "string"
    },
    "metadata": {
      "type": "object"
    },
    "created_at": {
      "type": "string",
      "format": "date-time"
    },
    "updated_at": {
      "type": "string",
      "format": "date-time"
    }
  }
}
```

## Examples

### Frequency Pattern

```json
{
  "id": "pat_001",
  "pattern_type": "frequency",
  "context_signature": "execute+backup+database:low_load",
  "success_rate": 0.85,
  "confidence": 0.92,
  "observation_count": 100,
  "extracted_from": "extract_20240115_0200",
  "metadata": {
    "action_type": "backup",
    "entity_class": "database",
    "typical_conditions": ["low_load", "off_hours"]
  },
  "created_at": "2024-01-15T02:00:00.000Z",
  "updated_at": "2024-01-15T02:00:00.000Z"
}
```

### Sequence Pattern

```json
{
  "id": "pat_002",
  "pattern_type": "sequence",
  "context_signature": "create+deploy+service:staging",
  "success_rate": 0.95,
  "confidence": 0.88,
  "observation_count": 50,
  "metadata": {
    "steps": ["validate", "build", "test", "deploy"],
    "common_sequence": ["test_before_deploy"]
  }
}
```

## Pattern Types

| Type | Description |
|------|-------------|
| `frequency` | Action types that commonly succeed/fail for entity classes |
| `sequence` | Common action sequences for intent classes |
| `correlation` | Context conditions that correlate with outcomes |

## Confidence Calculation

Confidence uses Bayesian smoothing to avoid overfitting to small sample sizes:

```python
confidence = (success_count + 1) / (observation_count + 2)
```