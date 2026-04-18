# Nexi Engine Architecture

Deep dive into the Nexi decision engine components.

## Engine Overview

Nexi is the decision engine that sits between Intent Parser and Plan Compiler. It generates N candidate plans, evaluates them against policies and memory context, and selects the best option.

## Sub-Components

```
                    ┌─────────────────────┐
                    │   Intent Interpreter │
                    └──────────┬────────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │   Option Generator  │
                    └──────────┬────────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │    Policy Filter    │
                    └──────────┬────────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │     Evaluator       │
                    └──────────┬────────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │  Decision Selector  │
                    └─────────────────────┘
```

## Component Details

### Intent Interpreter

**Purpose**: Parses raw Intent object into structured components for option generation.

**Inputs**:
- Intent object (intent_class, action_type, entity_class, parameters)

**Outputs**:
- Interpreted intent with extracted constraints, preferences, and context requirements

**Logic**:
1. Extract explicit constraints from parameters
2. Infer implicit constraints from intent_class
3. Identify relevant historical patterns
4. Prepare context manifest for option generation

### Option Generator

**Purpose**: Generates N candidate plans from interpreted intent using LLM.

**Inputs**:
- Interpreted intent
- Context manifest (recent contexts, relevant patterns)
- Configuration (N candidates, model settings)

**Outputs**:
- List of N candidate Plans

**Configuration**:
```yaml
nexi:
  max_candidates: 5  # Number of plans to generate
  model:
    temperature: 0.7
    max_tokens: 2048
```

**Prompt Template**:
```
Given intent: {intent}
Context: {context_manifest}
Generate {N} distinct plans to fulfill this intent.
Each plan should include:
- Step-by-step actions
- Expected outcomes
- Resource requirements
- Risk assessment
```

### Policy Filter

**Purpose**: Removes candidate plans that violate defined policies.

**Inputs**:
- List[Plan] from Option Generator
- Policy rules (YAML-defined)

**Outputs**:
- Filtered List[Plan] (policy-compliant only)

**Policy Definition**:
```yaml
policies:
  - name: no_delete_production
    description: "Prevent deletion of production resources"
    rule:
      - action_type: delete
        entity_class: production_resource
    action: reject
    
  - name: require_approval
    description: "Require human approval for high-risk actions"
    rule:
      - risk_score: ">0.7"
    action: require_human_approval
```

**Logic**:
1. Load policy rules from configured paths
2. For each candidate plan, check against all rules
3. Remove or flag plans violating policies
4. Log policy decisions for audit

### Evaluator

**Purpose**: Scores remaining candidates across four evaluation dimensions.

**Inputs**:
- Filtered List[Plan]
- Context (memory state, historical outcomes)

**Outputs**:
- List[EvaluatedPlan] with dimension scores

**Evaluation Dimensions**:

| Dimension | Description | Weight Default |
|-----------|-------------|-----------------|
| Safety | Does the plan cause harm? | 0.3 |
| Efficiency | Optimal resource usage? | 0.25 |
| Compliance | Follows policies and rules? | 0.25 |
| Context Fit | Matches current context? | 0.2 |

**Scoring Algorithm**:
```python
def evaluate(plan, context):
    safety_score = evaluate_safety(plan, context)
    efficiency_score = evaluate_efficiency(plan, context)
    compliance_score = evaluate_compliance(plan, context)
    context_fit_score = evaluate_context_fit(plan, context)
    
    weighted_score = (
        safety_score * 0.3 +
        efficiency_score * 0.25 +
        compliance_score * 0.25 +
        context_fit_score * 0.2
    )
    
    return EvaluatedPlan(
        plan=plan,
        scores={
            'safety': safety_score,
            'efficiency': efficiency_score,
            'compliance': compliance_score,
            'context_fit': context_fit_score
        },
        total_score=weighted_score
    )
```

### Decision Selector

**Purpose**: Selects the final plan from evaluated candidates.

**Inputs**:
- List[EvaluatedPlan]

**Outputs**:
- Selected Plan + Decision Token

**Selection Logic**:
1. Sort by total_score descending
2. Select top candidate
3. Generate unique decision_token
4. Log decision to audit ledger

**Tie-Breaking**:
- Prefer higher safety score
- Prefer lower estimated cost
- If still tied, use round-robin

## Error Handling

| Error | Handling |
|-------|----------|
| LLM timeout | Retry with exponential backoff, fallback to cached options |
| Policy parse error | Log error, continue with empty policy set |
| No valid candidates | Return error to caller, log to audit |
| Evaluation error | Exclude candidate, continue with others |