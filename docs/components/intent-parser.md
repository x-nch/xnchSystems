# Intent Parser

---
tags:
  - #component
  - #nexi
  - #decision
---

Converts raw user input into normalized Intent objects.

## Overview

The Intent Parser is the first processing step after input ingestion. It converts natural language or structured input into a normalized Intent object with classified intent_class, action_type, and entity_class.

## Input Types

### Natural Language

```bash
xnch execute "Create a backup of the production database"
```

### Structured Input

```bash
xnch execute --intent-class=execute --action-type=backup --entity-class=database --params='{"name": "production"}'
```

## Output: Intent Object

```python
class Intent:
    # Required fields
    raw_input: str                    # Original input
    intent_class: str                 # Classified intent (execute, query, create, etc.)
    action_type: str                  # Specific action (run_command, read_file, etc.)
    
    # Optional fields
    entity_class: str                 # Target entity type (file, service, data)
    parameters: Dict[str, Any]        # Extracted parameters
    confidence: float                 # Classification confidence (0.0-1.0)
    metadata: Dict[str, Any]          # Additional metadata
```

## Classification Categories

### Intent Classes

| Class | Description |
|-------|-------------|
| `execute` | Perform an action |
| `query` | Retrieve information |
| `create` | Create a new resource |
| `update` | Modify an existing resource |
| `delete` | Remove a resource |
| `analyze` | Perform analysis |
| `plan` | Create a plan |

### Action Types

| Category | Actions |
|----------|---------|
| Files | read_file, write_file, delete_file, copy_file, move_file |
| Commands | run_command, run_script, run_container |
| Data | backup, restore, migrate, sync |
| Services | deploy, scale, restart, stop |
| Configuration | set_config, get_config, validate_config |

### Entity Classes

| Class | Description |
|-------|-------------|
| `file` | Files and directories |
| `database` | Database instances |
| `service` | Running services |
| `container` | Docker containers |
| `config` | Configuration files |
| `data` | Data collections |

## Parsing Process

```
Raw Input
    │
    ▼
┌─────────────┐
│  Tokenize   │  Split into tokens/words
└─────────────┘
    │
    ▼
┌─────────────┐
│   Extract   │  Extract entities, parameters
│  Entities   │
└─────────────┘
    │
    ▼
┌─────────────┐
│  Classify   │  Determine intent_class, action_type
└─────────────┘
    │
    ▼
┌─────────────┐
│  Validate   │  Check required fields, confidence
└─────────────┘
    │
    ▼
   Intent
```

## Configuration

```yaml
intent_parser:
  # Minimum confidence threshold
  min_confidence: 0.7
  
  # Enable entity extraction
  extract_entities: true
  
  # Entity extraction patterns
  entity_patterns:
    database: "(production|staging|dev)\\s+(db|database)"
    service: "(api|web|worker|scheduler)"
```

## Custom Intent Classes

You can define custom intent classes in configuration:

```yaml
intent_parser:
  custom_classes:
    - name: "deploy_infrastructure"
      description: "Deploy infrastructure components"
      action_types:
        - apply_terraform
        - apply_helm
      keywords:
        - deploy
        - apply
        - provision
```

## Error Handling

| Error | Handling |
|-------|----------|
| Unparseable input | Return error with suggestions |
| Low confidence (<0.7) | Prompt user for clarification |
| Unknown intent class | Map to closest known class with flag |