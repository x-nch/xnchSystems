"""Pipeline migration tools for Phase 3: LangGraph StateGraph."""

from pathlib import Path
from langchain.tools import tool

CODEBASE_ROOT = Path("/Users/xnch/xnchSystems")


@tool(parse_docstring=True)
def define_decision_state() -> str:
    """Define the DecisionState TypedDict for the LangGraph pipeline.

    Maps all pipeline step inputs/outputs to a single state schema.
    """
    state_code = '''"""DecisionState — LangGraph state for the XNCH/Nexi decision pipeline."""
from typing import TypedDict, Annotated, Any
import operator
from uuid import UUID


class Intent(TypedDict):
    intent_class: str  # QUERY | DECISION | EXECUTION | ESCALATION
    action_type: str
    target_entity_id: str
    target_entity_class: str
    urgency: str
    ambiguity_score: float
    raw_input: str


class AssembledContext(TypedDict):
    system_prompt: str
    recent_turns: list[dict]
    relevant_episodes: list[str]
    entity_context: list[dict]
    relationship_context: list[dict]
    perception_snippets: list[str]


class PolicyVerdict(TypedDict):
    verdict: str  # ALLOW | ALLOW_WITH_WARNINGS | MODIFY | DEFER | BLOCK
    policy_refs: list[str]
    warnings: list[str]
    modified_action_spec: dict[str, Any] | None


class EvaluatedOption(TypedDict):
    option_id: str
    policy_verdict: str
    composite_score: float
    simulation_required: bool


class PlanOption(TypedDict):
    option_id: str
    action_type: str
    action_spec: dict[str, Any]
    reversible: bool
    estimated_side_effects: list[str]


class DecisionState(TypedDict):
    # Input
    raw_input: str
    session_id: str
    trace_id: str

    # After classify_intent
    intent: Intent

    # After assemble_context
    context: AssembledContext

    # After generate_options
    options: list[PlanOption]

    # After filter_policy
    policy_verdicts: list[PolicyVerdict]

    # After evaluate
    evaluated: list[EvaluatedOption]

    # After select
    selected: PlanOption | None

    # After compile_plan
    compiled_plan: dict[str, Any] | None

    # Audit trail
    events: Annotated[list[dict], operator.add]
'''
    script_path = CODEBASE_ROOT / "xnch" / "xnch" / "agents" / "decision_state.py"
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(state_code)
    return f"DecisionState written to {script_path}"


@tool(parse_docstring=True)
def create_langgraph_pipeline() -> str:
    """Create the LangGraph StateGraph pipeline.

    Converts the sequential pipeline to a graph with conditional routing.
    """
    pipeline_code = '''"""LangGraph decision pipeline for XNCH/Nexi."""
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.types import interrupt

from .decision_state import DecisionState


async def classify_intent(state: DecisionState) -> dict:
    """Node: classify user intent (maps from intent_interpreter.py)."""
    from nexi.pipeline.intent_interpreter import IntentInterpreter
    from uuid import UUID

    interpreter = IntentInterpreter()
    intent = await interpreter.interpret(
        raw_input=state["raw_input"],
        session_id=UUID(state["session_id"]),
        trace_id=state["trace_id"],
    )
    return {"intent": intent}


async def assemble_context(state: DecisionState) -> dict:
    """Node: assemble context (maps from context_assembler.py)."""
    from nexi.pipeline.context_assembler import assemble_context

    ctx = await assemble_context(
        session_id=state["session_id"],
        raw_input=state["raw_input"],
        working_memory=None,  # Inject from runtime
        pg_episodic=None,     # Inject from runtime
        graph_store=None,     # Inject from runtime (now Memgraph)
        relationship_store=None,
        sensory_buffer=None,
    )
    return {"context": ctx}


async def generate_options(state: DecisionState) -> dict:
    """Node: generate plan options (maps from option_generator.py)."""
    from nexi.pipeline.option_generator import OptionGenerator

    generator = OptionGenerator()
    options = await generator.generate(
        intent=state["intent"],
        context=state["context"],
    )
    return {"options": options}


async def filter_policy(state: DecisionState) -> dict:
    """Node: filter options through policy engine (maps from policy_filter.py)."""
    from nexi.pipeline.policy_filter import PolicyFilter

    filter_ = PolicyFilter()
    verdicts = []
    for opt in state["options"]:
        verdict = filter_.evaluate(
            intent=state["intent"],
            option=opt,
        )
        verdicts.append(verdict)
    return {"policy_verdicts": verdicts}


def route_after_policy(state: DecisionState) -> str:
    """Conditional edge: route based on policy verdicts."""
    for v in state["policy_verdicts"]:
        if v.get("verdict") == "BLOCK":
            return "end"
    return "evaluate"


async def evaluate(state: DecisionState) -> dict:
    """Node: score and evaluate options (maps from evaluator.py)."""
    from nexi.pipeline.evaluator import Evaluator

    evaluator = Evaluator()
    evaluated = evaluator.score(
        options=list(zip(state["options"], state["policy_verdicts"])),
        intent=state["intent"],
        manifest=state["context"],
        session={"trace_id": state["trace_id"]},
    )
    return {"evaluated": evaluated}


async def select(state: DecisionState) -> dict:
    """Node: select best option (maps from selector.py). May interrupt for human approval."""
    from nexi.pipeline.selector import Selector

    selector = Selector()
    selected = selector.select(
        evaluated=state["evaluated"],
        options=state["options"],
    )

    # Human-in-the-loop for EXECUTION actions
    if state["intent"].get("intent_class") == "EXECUTION":
        approved = interrupt({
            "action": "approve_execution",
            "selected": selected,
            "intent": state["intent"],
        })
        if not approved:
            return {"selected": None}

    return {"selected": selected}


def route_after_select(state: DecisionState) -> str:
    """Conditional edge: route based on selection."""
    if state.get("selected") is None:
        return "end"
    return "compile_plan"


async def compile_plan(state: DecisionState) -> dict:
    """Node: compile selected option into executable plan."""
    from nexi.pipeline.plan_compiler import PlanCompiler

    compiler = PlanCompiler()
    plan = compiler.compile(
        option=state["selected"],
        intent=state["intent"],
        context=state["context"],
    )
    return {"compiled_plan": plan}


async def dispatch(state: DecisionState) -> dict:
    """Node: dispatch plan for execution."""
    # Dispatch logic here
    return {"events": [{"type": "dispatched", "plan": state.get("compiled_plan")}]}
    # Placeholder — actual dispatch calls execution runner


def create_pipeline(checkpointer=None):
    """Build and compile the LangGraph decision pipeline."""
    graph = StateGraph(DecisionState)

    # Add nodes
    graph.add_node("classify_intent", classify_intent)
    graph.add_node("assemble_context", assemble_context)
    graph.add_node("generate_options", generate_options)
    graph.add_node("filter_policy", filter_policy)
    graph.add_node("evaluate", evaluate)
    graph.add_node("select", select)
    graph.add_node("compile_plan", compile_plan)
    graph.add_node("dispatch", dispatch)

    # Add edges
    graph.add_edge(START, "classify_intent")
    graph.add_edge("classify_intent", "assemble_context")
    graph.add_edge("assemble_context", "generate_options")
    graph.add_edge("generate_options", "filter_policy")
    graph.add_conditional_edges("filter_policy", route_after_policy, {
        "evaluate": "evaluate",
        "end": END,
    })
    graph.add_edge("evaluate", "select")
    graph.add_conditional_edges("select", route_after_select, {
        "compile_plan": "compile_plan",
        "end": END,
    })
    graph.add_edge("compile_plan", "dispatch")
    graph.add_edge("dispatch", END)

    return graph.compile(checkpointer=checkpointer)
'''
    script_path = CODEBASE_ROOT / "xnch" / "xnch" / "agents" / "pipeline_graph.py"
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(pipeline_code)
    return f"LangGraph pipeline written to {script_path}"


@tool(parse_docstring=True)
def add_human_in_the_loop() -> str:
    """Document the human-in-the-loop interrupt points in the pipeline.

    Interrupts are already added in create_langgraph_pipeline for:
    - EXECUTION actions requiring approval
    - Policy DEFER verdicts (can be added)
    - Ambiguous intents (can be added)
    """
    hitl_doc = '''# Human-in-the-Loop Configuration

## Current Interrupt Points

### 1. EXECUTION Action Approval
Location: `pipeline_graph.py` → `select()` node

When intent_class is EXECUTION, the pipeline pauses and asks for human approval.
Resume with `Command(resume=True)` or `Command(resume=False)`.

### 2. Policy DEFER (Recommended Addition)
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

### 3. Ambiguous Intent (Recommended Addition)
Add to `classify_intent()` node:

```python
if intent.get("ambiguity_score", 0) > 0.7:
    clarified = interrupt({
        "action": "clarify_intent",
        "questions": intent.get("clarifications_needed", []),
        "raw_input": state["raw_input"],
    })
    # Update intent with clarified values
```

## Resume Commands

```python
from langgraph.types import Command

# Resume with approval
graph.invoke(Command(resume=True), config)

# Resume with edited response
graph.invoke(Command(resume={"approved": True, "edited_response": "..."}), config)
```
'''
    doc_path = CODEBASE_ROOT / "docs" / "human-in-the-loop.md"
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.write_text(hitl_doc)
    return f"HITL documentation written to {doc_path}"


@tool(parse_docstring=True)
def validate_pipeline_migration() -> str:
    """Validate pipeline migration by comparing old and new pipeline outputs.

    Runs identical inputs through both pipelines and compares results.
    """
    validation_code = '''"""Validate pipeline migration — compare old vs new pipeline."""
import asyncio
from uuid import uuid4

async def validate():
    test_inputs = [
        "list all services",
        "deploy the staging environment",
        "analyze database performance",
        "escalate to human operator",
    ]

    from nexi.pipeline.intent_interpreter import IntentInterpreter
    from xnch.agents.pipeline_graph import create_pipeline

    old_interpreter = IntentInterpreter()
    new_pipeline = create_pipeline()

    for raw_input in test_inputs:
        session_id = str(uuid4())
        trace_id = str(uuid4())

        # Old pipeline
        old_intent = await old_interpreter.interpret(raw_input, uuid4(session_id), trace_id)

        # New pipeline (just classify_intent node)
        result = new_pipeline.invoke({
            "raw_input": raw_input,
            "session_id": session_id,
            "trace_id": trace_id,
        })
        new_intent = result.get("intent", {})

        match = old_intent.get("intent_class") == new_intent.get("intent_class")
        status = "PASS" if match else "FAIL"
        print(f"[{status}] '{raw_input}': old={old_intent.get('intent_class')}, new={new_intent.get('intent_class')}")

asyncio.run(validate())
'''
    script_path = CODEBASE_ROOT / "scripts" / "validate_pipeline.py"
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(validation_code)
    return f"Pipeline validation script written to {script_path}. Run with: python {script_path}"
