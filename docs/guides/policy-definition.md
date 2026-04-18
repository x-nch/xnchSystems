# Policy Definition

Define policies for Nexi to enforce.

## Overview

Policies define rules that Nexi uses to filter and evaluate candidate plans. They are defined in YAML and loaded at startup.

## Policy Structure

```yaml
version: "1.0"
name: "my-policies"
description: "Custom policy definitions"

policies:
  - name: policy_name
    description: "What this policy does"
    rule:
      # Matching conditions
      - condition: expression
    action: action_type
    priority: 1  # Higher = evaluated first
```

## Rule Conditions

### Basic Conditions

```yaml
rule:
  - action_type: delete
  - intent_class: execute
  - entity_class: production
```

### Comparisons

```yaml
rule:
  - risk_score: ">0.7"
  - estimated_cost: "<100"
  - confidence: ">=0.8"
```

### Multiple Conditions (AND)

```yaml
rule:
  - action_type: delete
    entity_class: production
    # Both must match
```

### Multiple Rules (OR)

```yaml
rule:
  - action_type: delete
  - action_type: drop
  # Either matches
```

## Actions

| Action | Description |
|--------|-------------|
| `reject` | Remove from candidate list |
| `require_human_approval` | Pause for approval |
| `flag` | Mark for review |
| `modify` | Modify candidate before evaluation |

## Example Policies

### Prevent Production Deletes

```yaml
policies:
  - name: no_production_deletes
    description: "Prevent deletion of production resources"
    rule:
      - action_type: delete
        entity_class: production
    action: reject
    priority: 10
```

### Require Approval for High Risk

```yaml
policies:
  - name: require_approval_high_risk
    description: "Require human approval for high-risk actions"
    rule:
      - risk_score: ">0.7"
    action: require_human_approval
    priority: 5
```

### Cost Limits

```yaml
policies:
  - name: cost_limit
    description: "Reject plans exceeding cost threshold"
    rule:
      - estimated_cost: ">500"
    action: reject
```

### Environment-Specific Rules

```yaml
policies:
  - name: staging_deploy
    description: "Allow deploys to staging without approval"
    rule:
      - action_type: deploy
        entity_environment: staging
    action: allow  # No restriction
    
  - name: production_deploy
    description: "Require approval for production deploys"
    rule:
      - action_type: deploy
        entity_environment: production
    action: require_human_approval
```

## Priority

Policies are evaluated in priority order (highest first):

```yaml
policies:
  - name: critical_rule
    priority: 100
    ...
  - name: normal_rule
    priority: 1
    ...
```

## Loading Policies

```yaml
nexi:
  policy_paths:
    - ~/.xnch/policies/default.yaml
    - ~/.xnch/policies/custom.yaml
```

## Testing Policies

```bash
# Validate policy syntax
xnch policy validate ./policies.yaml

# Test against sample intent
xnch policy test ./policies.yaml --intent="Delete production database"
```

## Policy Management

```bash
# List loaded policies
xnch policy list

# Reload policies
xnch policy reload
```