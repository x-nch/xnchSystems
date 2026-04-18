# Human Approval Gate

---
tags:
  - #guide
  - #policy
---

Require human approval before execution.

## Overview

The Human Approval Gate pauses execution and requires explicit user confirmation before proceeding. This is useful for:
- High-risk operations
- Production environment changes
- Cost-sensitive operations

## Configuration

### Via Policy

Define in your policy file:

```yaml
policies:
  - name: require_approval_production
    description: "Require human approval for production changes"
    rule:
      - entity_environment: production
        action_type: [delete, deploy, modify]
    action: require_human_approval
    
  - name: require_approval_high_risk
    description: "Require approval for high-risk actions"
    rule:
      - risk_score: ">0.7"
    action: require_human_approval
```

### Via CLI Flag

```bash
xnch execute "Deploy to production" --require-approval
```

### Via Code

```python
result = engine.execute(
    intent,
    require_approval=True
)
```

## Interactive Mode

When approval is required, the CLI prompts:

```
⚠️  Approval Required

Action: Deploy to production
Plan: Rolling update to 5 instances
Risk Score: 0.75

Estimated Impact:
  - Downtime: ~30 seconds (rolling)
  - Resources: 2 new instances ($0.10/hr)

Continue? [y/N]: y
```

## Non-Interactive Mode

For CI/CD pipelines, use environment variable or timeout:

```bash
# Auto-approve (for trusted pipelines)
XNCH_AUTO_APPROVE=true xnch execute "..."

# Timeout (fail if not approved within time)
xnch execute "..." --approval-timeout=300
```

## Custom Approval Messages

```python
result = engine.execute(
    intent,
    approval_message="⚠️ This will delete all data in the database. Continue?",
    approval_timeout=600
)
```

## Audit Trail

All approval decisions are logged:

```json
{
  "event_type": "approval_requested",
  "decision_id": "dec_abc123",
  "approved": true,
  "approved_by": "user@hostname",
  "approval_time": "2024-01-15T10:30:00Z"
}
```