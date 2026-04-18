# Error Codes

API error code reference.

## Error Response Format

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message",
    "details": {...}
  }
}
```

## Error Codes

### Validation Errors (4xx)

| Code | HTTP | Description |
|------|------|-------------|
| `INVALID_INPUT` | 400 | Invalid request body |
| `PARSE_ERROR` | 400 | Could not parse input |
| `MISSING_FIELD` | 400 | Required field missing |
| `INVALID_FIELD` | 400 | Field has invalid value |
| `NOT_FOUND` | 404 | Resource not found |
| `CONFLICT` | 409 | Resource already exists |
| `RATE_LIMITED` | 429 | Too many requests |

### Authentication Errors

| Code | HTTP | Description |
|------|------|-------------|
| `UNAUTHORIZED` | 401 | No credentials provided |
| `FORBIDDEN` | 403 | Insufficient permissions |
| `INVALID_API_KEY` | 401 | API key invalid |
| `TOKEN_EXPIRED` | 401 | JWT token expired |

### Execution Errors

| Code | HTTP | Description |
|------|------|-------------|
| `EXECUTION_FAILED` | 500 | Plan execution failed |
| `EXECUTION_TIMEOUT` | 504 | Execution timed out |
| `NO_CANDIDATES` | 500 | No valid candidates |
| `APPROVAL_REJECTED` | 403 | Human rejected execution |

### Model Errors

| Code | HTTP | Description |
|------|------|-------------|
| `MODEL_UNAVAILABLE` | 503 | Model endpoint down |
| `MODEL_TIMEOUT` | 504 | Model request timeout |
| `MODEL_ERROR` | 500 | Model returned error |

### Memory Errors

| Code | HTTP | Description |
|------|------|-------------|
| `STORE_ERROR` | 500 | Database error |
| `STORE_CONNECTION` | 503 | Cannot connect to store |
| `VECTOR_ERROR` | 500 | Vector index error |

## Examples

### 400 Invalid Input

```json
{
  "error": {
    "code": "INVALID_INPUT",
    "message": "Invalid execution options",
    "details": {
      "field": "options.dry_run",
      "reason": "must be boolean"
    }
  }
}
```

### 401 Unauthorized

```json
{
  "error": {
    "code": "UNAUTHORIZED",
    "message": "API key required"
  }
}
```

### 500 Execution Failed

```json
{
  "error": {
    "code": "EXECUTION_FAILED",
    "message": "Command execution failed",
    "details": {
      "step": "run_backup",
      "error": "database connection refused"
    }
  }
}
```