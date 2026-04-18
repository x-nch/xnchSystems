# Nexi Engine

The policy-aware multi-option decision engine.

## Overview

Nexi is the decision engine that sits between Intent Parser and Plan Compiler. It generates N candidate plans, evaluates them against policies and memory context, and selects the best option.

## Sub-Components

The Nexi Engine consists of five sub-components:

1. **Intent Interpreter** - Prepares intent for option generation
2. **Option Generator** - Generates N candidate plans via LLM
3. **Policy Filter** - Removes candidates violating policies
4. **Evaluator** - Scores candidates across four dimensions
5. **Decision Selector** - Selects final plan

## Usage

```python
from xnch.nexi import NexiEngine

engine = NexiEngine(config)

# Execute full pipeline
result = engine.execute(intent)
# Returns: (SelectedPlan, DecisionToken, AllCandidates)
```

## Configuration

```yaml
nexi:
  max_candidates: 5
  
  # Option generation
  option_generator:
    temperature: 0.7
    max_tokens: 2048
    top_p: 0.9
    
  # Evaluation weights
  evaluation:
    weights:
      safety: 0.30
      efficiency: 0.25
      compliance: 0.25
      context_fit: 0.20
      
  # Policy paths
  policy_paths:
    - ~/.xnch/policies/default.yaml
    - ~/.xnch/policies/custom.yaml
```

## Detailed Components

### Intent Interpreter

Prepares the intent for option generation by extracting constraints and preparing context.

### Option Generator

Uses the Model Adapter to generate candidate plans:

```python
def generate_options(intent, context):
    prompt = build_prompt(intent, context)
    response = model_adapter.generate(prompt)
    plans = parse_plans(response)
    return plans
```

### Policy Filter

Filters candidates against defined policies:

```yaml
policies:
  - name: no_destructive_production
    rule:
      action_type: delete
      entity_class: production
    action: reject
    
  - name: require_confirmation
    rule:
      risk_score: ">0.7"
    action: require_human_approval
```

### Evaluator

Scores across dimensions:

| Dimension | Description |
|-----------|-------------|
| Safety | No harmful side effects |
| Efficiency | Optimal resource usage |
| Compliance | Follows policies/rules |
| Context Fit | Matches current context |

### Decision Selector

Selects highest-scoring plan, generates decision token.

## API Reference

```python
class NexiEngine:
    def __init__(self, config: NexiConfig):
        ...
        
    def execute(self, intent: Intent) -> NexiResult:
        """Execute full decision pipeline."""
        
    def generate_options(self, intent: Intent) -> List[Plan]:
        """Generate candidate plans only."""
        
    def evaluate(self, plans: List[Plan]) -> List[EvaluatedPlan]:
        """Evaluate plans without generating new options."""
        
    def select(self, evaluated: List[EvaluatedPlan]) -> Tuple[Plan, str]:
        """Select final plan, return (plan, decision_token)."""
```