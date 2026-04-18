# Reviewing Policy Candidates

---
tags:
  - #guide
  - #learning
---

Review and apply policy suggestions from the learning system.

## Overview

The learning system generates policy candidates based on observed failure patterns. These candidates require human review before being applied.

## Finding Candidates

```bash
# List pending candidates
xnch learning candidates
```

### Output

```
Policy Candidates

┌──────┬────────────────────────────┬─────────────┬──────────┐
│ ID   │ Description                │ Confidence  │ Based On │
├──────┼────────────────────────────┼─────────────┼──────────┤
│ pc1  │ Prevent backup on Fridays  │ 80%         │ 15 fails │
│ pc2  │ Require approval for prod  │ 65%         │ 8 fails  │
│ pc3  │ Block delete + database    │ 90%         │ 22 fails │
└──────┴────────────────────────────┴─────────────┴──────────┘
```

## Reviewing a Candidate

```bash
# View candidate details
xnch learning candidates show pc1
```

### Output

```
Candidate: pc1
Description: Prevent backup on Fridays

Rule:
  action_type: backup
  day_of_week: Friday

Based on:
  - 15 failures out of 20 attempts on Fridays
  - Success rate: 25%
  
Context: Most failures occurred during high-load periods

Recommended action: reject
```

## Applying Candidates

### Apply as-is

```bash
xnch learning candidates apply pc1
```

This adds the policy to your active policies.

### Apply with Modification

```bash
xnch learning candidates apply pc1 --modify='{"action": "require_human_approval"}'
```

### Reject

```bash
xnch learning candidates reject pc1 --reason="Business requirement"
```

## Bulk Operations

### Apply Multiple

```bash
xnch learning candidates apply pc1 pc2 pc3
```

### Apply All Safe (Confidence > 80%)

```bash
xnch learning candidates apply --min-confidence=0.8
```

## Review Workflow

### 1. Regular Review

Set up regular review cadence:

```bash
# Weekly review reminder
0 9 * * 1 xnch learning candidates
```

### 2. Auto-Apply Safe Candidates

```yaml
learning:
  policy_candidates:
    auto_apply: true
    min_confidence: 0.9  # Only very confident ones
```

### 3. Logging

All review decisions are logged:

```json
{
  "event_type": "policy_candidate_reviewed",
  "candidate_id": "pc1",
  "action": "applied",
  "reviewer": "admin",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## Best Practices

1. **Review weekly** - Don't let candidates pile up
2. **Check context** - Understand why the pattern was detected
3. **Start conservative** - Use `require_human_approval` before `reject`
4. **Document reasons** - Why you accepted or rejected