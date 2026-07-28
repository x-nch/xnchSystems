# Phase 3: Pipeline Migration to LangGraph

## Tools
- `define_decision_state` — Create DecisionState TypedDict
- `create_langgraph_pipeline` — Build StateGraph with all nodes
- `add_human_in_the_loop` — Document interrupt points
- `validate_pipeline_migration` — Compare old vs new pipeline outputs

## Acceptance Criteria
- [ ] DecisionState covers all pipeline step inputs/outputs
- [ ] StateGraph has all 8 nodes connected
- [ ] Interrupt points for EXECUTION actions working
- [ ] validate_pipeline_migration passes for all test inputs
- [ ] Old sequential pipeline importable for backward compat

## Pipeline Nodes
```
START → classify_intent → assemble_context → generate_options
    → filter_policy → [evaluate | END]
    → evaluate → select → [compile_plan | END]
    → compile_plan → dispatch → END
```
