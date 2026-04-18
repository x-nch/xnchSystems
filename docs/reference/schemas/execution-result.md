# ExecutionResult Schema

---
tags:
  - #reference
  - #contracts
  - #execution
---

Outcome of plan execution.

## Definition

```python
class ExecutionResult:
    execution_id: str               # Unique execution identifier
    plan_id: str                   # Reference to executed plan
    status: str                    # success, failure, partial
    steps: List[StepResult]        # Per-step results
    duration_ms: int               # Total execution time
    started_at: datetime           # Execution start time
    completed_at: datetime         # Execution completion time
    error: Optional[str]           # Error message if failed
    metadata: Dict[str, Any]       # Additional metadata


class StepResult:
    step_id: str                   # Reference to step
    status: str                   # success, failure, skipped
    output: Optional[Any]          # Step output
    error: Optional[str]          # Error message if failed
    duration_ms: int               # Step execution time
    started_at: datetime          # Step start time
    completed_at: datetime        # Step completion time
```

## JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["execution_id", "plan_id", "status", "steps", "duration_ms"],
  "properties": {
    "execution_id": {
      "type": "string"
    },
    "plan_id": {
      "type": "string"
    },
    "status": {
      "type": "string",
      "enum": ["success", "failure", "partial"]
    },
    "steps": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["step_id", "status", "duration_ms"],
        "properties": {
          "step_id": {"type": "string"},
          "status": {"type": "string", "enum": ["success", "failure", "skipped"]},
          "output": {},
          "error": {"type": "string"},
          "duration_ms": {"type": "integer"},
          "started_at": {"type": "string", "format": "date-time"},
          "completed_at": {"type": "string", "format": "date-time"}
        }
      }
    },
    "duration_ms": {
      "type": "integer"
    },
    "started_at": {
      "type": "string",
      "format": "date-time"
    },
    "completed_at": {
      "type": "string",
      "format": "date-time"
    },
    "error": {"type": "string"},
    "metadata": {"type": "object"}
  }
}
```

## Examples

### Success

```json
{
  "execution_id": "exec_abc123",
  "plan_id": "plan_001",
  "status": "success",
  "steps": [
    {
      "step_id": "step_1",
      "status": "success",
      "output": "Backup created: backup_20240115.sql",
      "duration_ms": 4523
    },
    {
      "step_id": "step_2",
      "status": "success",
      "output": "Compressed: backup_20240115.sql.gz",
      "duration_ms": 1234
    }
  ],
  "duration_ms": 5757,
  "started_at": "2024-01-15T10:30:00.000Z",
  "completed_at": "2024-01-15T10:30:05.757Z"
}
```

### Failure

```json
{
  "execution_id": "exec_def456",
  "plan_id": "plan_002",
  "status": "failure",
  "steps": [
    {
      "step_id": "step_1",
      "status": "failure",
      "error": "Connection refused to database",
      "duration_ms": 5000
    }
  ],
  "duration_ms": 5000,
  "started_at": "2024-01-15T10:30:00.000Z",
  "completed_at": "2024-01-15T10:30:05.000Z",
  "error": "Database connection failed"
}
```

## Status Values

| Status | Description |
|--------|-------------|
| `success` | All steps completed successfully |
| `failure` | One or more steps failed |
| `partial` | Some steps completed, some skipped |