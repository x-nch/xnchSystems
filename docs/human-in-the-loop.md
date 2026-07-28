# Human-in-the-Loop Configuration

## Interrupt Points in LangGraph Pipeline

### 1. EXECUTION Action Approval
Location: `xnch/agents/pipeline_graph.py` → `select()` node

When `intent_class` is EXECUTION, the pipeline pauses and asks for human approval.
Resume with `Command(resume=True)` or `Command(resume=False)`.

### 2. Policy DEFER (Recommended)
Add to `filter_policy()` node:

```python
for v in verdicts:
    if v.get("verdict") == "DEFER":
        approved = interrupt({
            "action": "approve_deferred",
            "verdict": v,
            "option": opt,
        })
        if not approved:
            v["verdict"] = "BLOCK"
```

### 3. Ambiguous Intent (Recommended)
Add to `classify_intent()` node:

```python
if intent.get("ambiguity_score", 0) > 0.7:
    clarified = interrupt({
        "action": "clarify_intent",
        "questions": intent.get("clarifications_needed", []),
        "raw_input": state["raw_input"],
    })
```

## Resume Commands

```python
from langgraph.types import Command

# Resume with approval
graph.invoke(Command(resume=True), config)

# Resume with edited response
graph.invoke(Command(resume={"approved": True, "edited_response": "..."}), config)
```

## Checkpointing

The pipeline uses `PostgresSaver` for state persistence. Each node execution
is checkpointed, allowing:
- Resume after crashes
- Time-travel debugging
- Human-in-the-loop at any point
