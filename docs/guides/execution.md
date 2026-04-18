# Basic Execution

---
tags:
  - #guide
  - #execution
---

Learn how to execute your first intent through xnch + Nexi.

## Quick Start

```bash
xnch execute "Create a backup of the production database"
```

## Step-by-Step

### 1. Input Ingestion

Your input is received by the CLI or API:

```bash
xnch execute "Your intent here"
```

### 2. Intent Parsing

The Intent Parser converts your input to a normalized Intent:

```
Input: "Create a backup of the production database"
Intent: {
  intent_class: "create",
  action_type: "backup",
  entity_class: "database",
  parameters: {"environment": "production"}
}
```

### 3. Context Load

Memory context is loaded to inform option generation:

- Recent similar intents
- Relevant patterns from pattern store
- Historical outcomes

### 4. Option Generation

The Model Adapter generates N candidate plans (default: 5):

```
Plan 1: mysqldump + gzip + ssh to backup server
Plan 2: pg_dump + s3 upload
Plan 3: RDS snapshot + cross-region copy
...
```

### 5. Policy Filter

Candidates violating policies are removed:

```yaml
# If you have a policy preventing production deletes
- Some plans may be filtered out
```

### 6. Evaluation

Remaining candidates are scored across dimensions:

| Plan | Safety | Efficiency | Compliance | Context Fit | Total |
|------|--------|------------|------------|-------------|-------|
| Plan 1 | 0.95 | 0.85 | 0.90 | 0.80 | 0.875 |
| Plan 2 | 0.90 | 0.90 | 0.95 | 0.75 | 0.875 |

### 7. Decision Selection

Highest-scoring plan is selected:

```
Selected: Plan 1 (mysqldump approach)
Decision Token: tok_abc123
```

### 8. Human Gate (if required)

If policy requires approval, prompt appears:

```
⚠️ This plan will execute on PRODUCTION database
Continue? [y/N]: y
```

### 9. Execution

Plan is executed step-by-step:

```
Step 1: Connect to database server
Step 2: Run mysqldump
Step 3: Compress backup
Step 4: Transfer to backup location
Step 5: Verify backup integrity
```

### 10. Memory Write-back

Outcome recorded to memory stores:

```
Outcome: SUCCESS
Duration: 45.2s
Written to: Outcome Store, Episodic Store
```

## Viewing Results

```bash
# View last execution
xnch execute "..." --verbose

# View decision details
xnch audit decisions --last

# View memory stats
xnch memory stats
```

## Next Steps

- [Dry Run Mode](dry-run.md) - Test without executing
- [Policy Definition](policy-definition.md) - Define your policies
- [Monitoring](monitoring.md) - Set up observability