# Plan Schema

Candidate plan structure.

## Definition

```python
class Plan:
    plan_id: str                     # Unique identifier
    intent_hash: str                 # Hash of source intent
    steps: List[Step]                # Ordered execution steps
    estimated_cost: float            # Estimated resource cost
    risk_score: float               # Risk assessment (0.0-1.0)
    metadata: Dict[str, Any]         # Additional plan metadata


class Step:
    step_id: str                     # Unique step identifier
    type: str                        # Step type (command, http, file, api, wait)
    action: str                      # Specific action
    params: Dict[str, Any]           # Step parameters
    retry: Optional[RetryConfig]     # Retry configuration
    timeout: int                     # Timeout in seconds
    on_error: str                    # Error action (fail, retry, skip, fallback)


class RetryConfig:
    max_attempts: int               # Maximum retry attempts
    backoff: str                    # Backoff strategy (fixed, exponential)
    initial_delay: float             # Initial delay in seconds
    max_delay: float                 # Maximum delay in seconds
```

## JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["plan_id", "intent_hash", "steps"],
  "properties": {
    "plan_id": {
      "type": "string",
      "description": "Unique plan identifier"
    },
    "intent_hash": {
      "type": "string",
      "description": "Hash of source intent"
    },
    "steps": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["step_id", "type", "action"],
        "properties": {
          "step_id": {"type": "string"},
          "type": {"type": "string", "enum": ["command", "http", "file", "api", "wait"]},
          "action": {"type": "string"},
          "params": {"type": "object"},
          "timeout": {"type": "integer", "default": 60},
          "on_error": {"type": "string", "enum": ["fail", "retry", "skip", "fallback"]}
        }
      }
    },
    "estimated_cost": {
      "type": "number"
    },
    "risk_score": {
      "type": "number",
      "minimum": 0.0,
      "maximum": 1.0
    },
    "metadata": {
      "type": "object"
    }
  }
}
```

## Examples

### Simple Plan

```json
{
  "plan_id": "plan_001",
  "intent_hash": "sha256:abc123",
  "steps": [
    {
      "step_id": "step_1",
      "type": "command",
      "action": "run_command",
      "params": {
        "command": "mysqldump -u root -p prod_db > backup.sql"
      },
      "timeout": 300
    },
    {
      "step_id": "step_2",
      "type": "command",
      "action": "run_command",
      "params": {
        "command": "gzip backup.sql"
      },
      "timeout": 60
    }
  ],
  "estimated_cost": 0.5,
  "risk_score": 0.3,
  "metadata": {
    "description": "mysqldump backup approach"
  }
}
```

### Plan with Retry

```json
{
  "plan_id": "plan_002",
  "steps": [
    {
      "step_id": "step_1",
      "type": "http",
      "action": "api_call",
      "params": {
        "url": "https://api.example.com/deploy",
        "method": "POST",
        "body": {"version": "2.0"}
      },
      "retry": {
        "max_attempts": 3,
        "backoff": "exponential",
        "initial_delay": 1.0,
        "max_delay": 30.0
      },
      "timeout": 60,
      "on_error": "retry"
    }
  ],
  "estimated_cost": 2.0,
  "risk_score": 0.7
}
```

## Step Types

| Type | Description |
|------|-------------|
| `command` | Execute shell command |
| `http` | Make HTTP request |
| `file` | File operation |
| `api` | Call internal API |
| `wait` | Wait for condition |