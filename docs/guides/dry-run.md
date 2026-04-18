# Dry Run Mode

Simulate execution without making changes.

## Overview

Dry run mode executes the full Nexi pipeline but stops before the execution step. This allows you to:
- Review the plan that would be executed
- Check decision reasoning
- Validate policies
- Test without side effects

## Usage

```bash
xnch execute "Create a backup" --dry-run
```

## Output

```
🔍 Dry Run Mode

Intent: Create a backup of production database

Generated 5 candidate plans:

┌──────┬─────────────────────────┬────────┬────────────┐
│ Plan │ Approach                │ Score  │ Risk       │
├──────┼─────────────────────────┼────────┼────────────┤
│  1   │ mysqldump + ssh        │ 0.875  │ Low        │
│  2   │ pg_dump + s3           │ 0.872  │ Low        │
│  3   │ RDS snapshot           │ 0.850  │ Medium     │
│  4   │ mariabackup            │ 0.820  │ Low        │
│  5   │ file system copy      │ 0.780  │ High       │
└──────┴─────────────────────────┴────────┴────────────┘

Selected: Plan 1
Reasoning:
  - Highest safety score (0.95)
  - Good efficiency (0.85)
  - Matches context (recent similar backups succeeded)

Evaluation Dimensions:
  - Safety: 0.95
  - Efficiency: 0.85
  - Compliance: 0.90
  - Context Fit: 0.80

⚠️ This is a dry run. No changes will be made.
```

## Show Candidates

To see all candidate plans in detail:

```bash
xnch execute "..." --dry-run --show-candidates
```

## Programmatic Usage

```python
from xnch.nexi import NexiEngine

engine = NexiEngine(config)

# Generate options without execution
intent = parser.parse("Create a backup")
candidates = engine.generate_options(intent)

# Evaluate without execution
evaluated = engine.evaluate(candidates)

# Select without execution
plan, token = engine.select(evaluated)

# Full dry run
result = engine.dry_run(intent)
```

## Use Cases

1. **Testing new policies** - Validate policy behavior without risk
2. **Debugging** - Understand why a specific plan was selected
3. **Learning** - See how the system responds to different inputs
4. **CI/CD** - Validate behavior in automated tests