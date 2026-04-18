# Intent Schema

---
tags:
  - #reference
  - #contracts
  - #decision
---

Normalized representation of user input.

## Definition

```python
class Intent:
    # Required fields
    raw_input: str                    # Original input string
    intent_class: str                 # Classified intent type
    action_type: str                  # Specific action to perform
    
    # Optional fields
    entity_class: Optional[str]       # Target entity type
    parameters: Optional[Dict[str, Any]]  # Extracted parameters
    confidence: float                 # Classification confidence (0.0-1.0)
    metadata: Optional[Dict[str, Any]]  # Additional metadata
```

## JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["raw_input", "intent_class", "action_type"],
  "properties": {
    "raw_input": {
      "type": "string",
      "description": "Original input string"
    },
    "intent_class": {
      "type": "string",
      "enum": ["execute", "query", "create", "update", "delete", "analyze", "plan"],
      "description": "Classified intent type"
    },
    "action_type": {
      "type": "string",
      "description": "Specific action to perform"
    },
    "entity_class": {
      "type": "string",
      "description": "Target entity type"
    },
    "parameters": {
      "type": "object",
      "description": "Extracted parameters"
    },
    "confidence": {
      "type": "number",
      "minimum": 0.0,
      "maximum": 1.0,
      "default": 1.0
    },
    "metadata": {
      "type": "object"
    }
  }
}
```

## Examples

### Basic Intent

```json
{
  "raw_input": "Create a backup of the database",
  "intent_class": "create",
  "action_type": "backup",
  "entity_class": "database",
  "confidence": 0.95
}
```

### Intent with Parameters

```json
{
  "raw_input": "Deploy version 2.0 to production",
  "intent_class": "execute",
  "action_type": "deploy",
  "entity_class": "service",
  "parameters": {
    "version": "2.0",
    "environment": "production",
    "strategy": "rolling"
  },
  "confidence": 0.92
}
```

## Intent Classes

| Class | Description |
|-------|-------------|
| `execute` | Perform an action |
| `query` | Retrieve information |
| `create` | Create a new resource |
| `update` | Modify an existing resource |
| `delete` | Remove a resource |
| `analyze` | Perform analysis |
| `plan` | Create a plan |

## Action Types

| Category | Actions |
|----------|---------|
| Files | read_file, write_file, delete_file, copy_file, move_file |
| Commands | run_command, run_script, run_container |
| Data | backup, restore, migrate, sync |
| Services | deploy, scale, restart, stop |
| Configuration | set_config, get_config, validate_config |