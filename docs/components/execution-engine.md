# Execution Engine

Plans execution and step orchestration.

## Overview

The Execution Engine takes an approved plan and executes it step-by-step, handling errors, monitoring, and result collection.

## Execution Flow

```
Approved Plan
    │
    ▼
┌─────────────┐
│  Validate   │  Check prerequisites
└─────────────┘
    │
    ▼
┌─────────────┐
│  Execute    │  Run each step
│   Steps     │
└─────────────┘
    │
    ▼
┌─────────────┐
│  Collect    │  Gather results
│   Results   │
└─────────────┘
    │
    ▼
   Result
```

## Usage

```python
from xnch.execution import ExecutionEngine

engine = ExecutionEngine(config)

# Execute plan
result = engine.execute(plan)

# Dry run (simulation)
result = engine.simulate(plan)
```

## Step Types

| Type | Description |
|------|-------------|
| command | Execute shell command |
| http | Make HTTP request |
| file | File operation |
| api | Call internal API |
| wait | Wait for condition |

## Step Definition

```python
class Step:
    step_id: str
    type: str                      # command, http, file, api, wait
    action: str                    # Specific action
    params: Dict[str, Any]         # Parameters
    retry: RetryConfig            # Retry policy
    timeout: int                   # Timeout in seconds
    on_error: ErrorAction         # Error handling
```

## Error Handling

### Retry Policies

```yaml
execution:
  retry:
    max_attempts: 3
    backoff: exponential
    initial_delay: 1s
    max_delay: 30s
    
  # Per-step override
  step_defaults:
    command:
      timeout: 60
    http:
      timeout: 30
```

### Error Actions

| Action | Description |
|--------|-------------|
| `fail` | Stop execution, mark as failure |
| `retry` | Retry the step |
| `skip` | Skip this step, continue |
| `fallback` | Run fallback step |

## Monitoring

```python
# Execution events
on_step_start: (step) -> None
on_step_complete: (step, result) -> None
on_step_error: (step, error) -> None
on_plan_complete: (result) -> None
```

## Result Structure

```python
class ExecutionResult:
    plan_id: str
    status: str                    # success, failure, partial
    steps: List[StepResult]
    duration_ms: int
    error: Optional[str]
    metadata: Dict[str, Any]


class StepResult:
    step_id: str
    status: str
    output: Any
    error: Optional[str]
    duration_ms: int
```