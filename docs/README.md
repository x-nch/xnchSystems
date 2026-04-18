# xnch + Nexi System Documentation

## System Overview

**xnch** is the cognitive control plane — a local-first, privacy-first system for executing multi-agent workflows with structured memory and audit logging.

**Nexi** is the decision engine — sits between Intent Parser and Plan Compiler, generates N candidate plans, evaluates against policies and memory, selects the best option.

These two systems work together to provide a complete pipeline: raw input → structured intent → multiple plan options → policy-evaluated decision → simulated execution → audited result.

---

## Table of Contents

1. [xnch (Control Plane)](#1-xnch-control-plane)
2. [Nexi (Decision Engine)](#2-nexi-decision-engine)
3. [Memory System](#3-memory-system)
4. [Execution Flow](#4-execution-flow-10-steps)

---

## 1. xnch (Control Plane)

xnch is the orchestrator. It handles CLI input, authorization, simulation, and execution dispatch.

### 1.1 CLI Entry Point (Typer + Rich)

**What it is:** The command-line interface powered by Typer (CLI framework) and Rich (terminal formatting).

**Key responsibilities:**
- Parse CLI arguments and flags
- Format output with Rich (tables, syntax highlighting, progress bars)
- Route commands to appropriate handlers

**How it works:**
```python
import typer
from rich.console import Console

app = typer.Typer()
console = Console()

@app.command()
def run(prompt: str, dry_run: bool = False):
    """Execute a prompt through the xnch pipeline."""
    console.print(f"[bold blue]xnch[/bold blue] processing: {prompt}")
    # Route to Intent Parser
```

**Example:**
```bash
xnch run "Analyze Q4 revenue and flag anomalies" --dry-run
```

---

### 1.2 Intent Parser

**What it is:** Converts raw user input (natural language) into normalized Intent objects.

**Key responsibilities:**
- Parse raw input into structured intent
- Extract entities, actions, and constraints
- Enrich intent with context from memory

**How it works:**
1. Receives raw string input
2. Runs NER (Named Entity Recognition) for entity extraction
3. Classifies action type (query, execute, analyze)
4. Builds Intent object with schema validation

**Code Example:**
```python
from pydantic import BaseModel
from enum import Enum

class ActionType(str, Enum):
    QUERY = "query"
    EXECUTE = "execute"
    ANALYZE = "analyze"

class Intent(BaseModel):
    raw_input: str
    action: ActionType
    entities: list[str]
    constraints: dict[str, any]
    confidence: float  # 0.0-1.0

def parse_intent(raw: str) -> Intent:
    # Simplified — actual impl uses NER + classifier
    return Intent(
        raw_input=raw,
        action=classify_action(raw),
        entities=extract_entities(raw),
        constraints={}
    )
```

---

### 1.3 Policy Gate

**What it is:** Authorization check that validates intents against defined policies before proceeding.

**Key responsibilities:**
- Load policy definitions from config
- Check intent against BLOCK/MODIFY/ALLOW rules
- Return policy decision with modifiers if any

**How it works:**
```python
class PolicyDecision(str, Enum):
    BLOCK = "block"
    MODIFY = "modify"
    ALLOW = "allow"

def check_policy(intent: Intent) -> PolicyDecision:
    # Load policies from YAML/JSON config
    # Match intent fields against rules
    # Return decision
```

**Example policies (YAML):**
```yaml
policies:
  - rule: " BLOCK if action == execute and 'delete' in entities"
  - rule: " MODIFY if cost_estimate > 10000"
```

---

### 1.4 Simulation Engine

**What it is:** Dry-runs execution plans to show what would happen before actual execution.

**Key responsibilities:**
- Execute plan in sandbox mode
- Collect side effects without committing
- Render diff showing planned changes

**How it works:**
```python
def simulate(plan: ExecutionPlan, context: Context) -> SimulationResult:
    # Walk plan DAG in dry-run mode
    # Capture all expected outputs
    # Calculate diff from current state
    return SimulationResult(
        diff=render_diff(expected_changes),
        risk_flags=identify_risks(plan),
        estimated_cost=calculate_cost(plan)
    )
```

**Output Example:**
```
=== SIMULATION ===
Plan: Update customer record
Changes:
  + email: "new@example.com" (was "old@example.com")
  + updated_at: "2026-04-18T10:30:00Z"
Risk flags: None
Estimated cost: 2 tokens
```

---

### 1.5 Executor

**What it is:** Walks the execution DAG, dispatches tasks to agents in topological order.

**Key responsibilities:**
- Build execution DAG from plan
- Resolve dependencies between tasks
- Dispatch to appropriate agents (AgentKit, tool calls, API endpoints)
- Handle failures with retry/logging

**How it works:**
```python
def execute(dag: list[Task], context: Context) -> ExecutionResult:
    # Topological sort
    ready = topological_sort(dag)
    
    for task in ready:
        if task.is_ready():
            result = dispatch(task, context)
            context.add_result(task.id, result)
            
    return aggregate_results(context)
```

---

### 1.6 REST/gRPC Gateway

**What it is:** Exposes xnch as a service endpoint for programmatic access.

**Key responsibilities:**
- Serve REST API (FastAPI)
- Serve gRPC for high-performance calls
- Handle authentication, rate limiting
- Versioned API contracts

**REST Example:**
```bash
# POST /v1/execute
curl -X POST http://localhost:8080/v1/execute \
  -H "Authorization: Bearer $XNCH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Analyze Q4 revenue"}'
```

**gRPC Example:**
```python
import grpc

stub = ExecutionServiceStub(channel)
response = stub.Execute.Execute(
    Prompt="Analyze Q4 revenue",
    Options={"dry_run": False}
)
```

---

## 2. Nexi (Decision Engine)

Nexi sits between Intent Parser and Plan Compiler. It generates options, evaluates them, and selects the best.

### 2.1 Architecture Overview

```
Intent → Intent Interpreter → Option Generator → Policy Filter → Evaluator → Decision Selector
                                        ↓
                                   Context Store
                                        ↓
                                   Vector Index
```

### 2.2 Intent Interpreter

**What it is:** Interprets the parsed Intent, loads relevant context from memory, prepares the context manifest.

**Key responsibilities:**
- Enrich intent with historical context
- Build context manifest for LLM prompt
- Flag critical constraints

**How it works:**
```python
def interpret(intent: Intent, memory: Memory) -> ContextManifest:
    # Semantic search for related past decisions
    history = memory.semantic_search(intent.raw_input, limit=5)
    
    # Build manifest
    return ContextManifest(
        intent=intent,
        past_decisions=history,
        constraints=load_constraints(intent),
        session_state=memory.get_session()
    )
```

---

### 2.3 Option Generator

**What it is:** Uses vLLM with guided_json to generate 3-7 plan options from the intent.

**Key responsibilities:**
- Generate multiple candidate plans (N = 3-7)
- Enforce JSON schema on outputs
- Ensure diversity in options

**How it works:**
```python
from vllm import LLM

llm = LLM(model="meta-llama/Llama-3.1-8b-Instruct")

def generate_options(manifest: ContextManifest, n: int = 5) -> list[PlanOption]:
    # Guided JSON mode
    prompt = build_prompt(manifest)
    
    outputs = llm.generate(
        prompt,
        guided_json=PlanOption.schema(),  # JSON Schema
        n=n
    )
    
    return [parse_json(o.text) for o in outputs]
```

**Output Schema:**
```json
{
  "plan_id": "plan_001",
  "description": "Query DB for revenue, aggregate by quarter",
  "steps": [
    {"agent": "db_agent", "action": "query", "params": {...}},
    {"agent": "analysis_agent", "action": "aggregate", "params": {...}}
  ],
  "estimated_cost": 150,
  "estimated_duration": "30s"
}
```

---

### 2.4 Policy Filter

**What it is:** Applies BLOCK/MODIFY/ALLOW to each plan option against policies.

**Key responsibilities:**
- Check each option against policy rules
- Return modified options if policy requires changes
- Reject options that violate BLOCK rules

**How it works:**
```python
def filter_options(options: list[PlanOption]) -> list[PlanOption]:
    allowed = []
    
    for opt in options:
        decision = evaluate_policy(opt)
        
        if decision == PolicyDecision.BLOCK:
            continue  # Reject
        elif decision == PolicyDecision.MODIFY:
            opt = apply_modifiers(opt)  # Adjust
            allowed.append(opt)
        else:
            allowed.append(opt)
    
    return allowed
```

---

### 2.5 Evaluator

**What it is:** Scores each option across 4 dimensions and selects the best.

**Key responsibilities:**
- Calculate 4 scores for each option
- Apply weighted aggregation
- Return ranked options

**Scoring Dimensions:**
| Dimension | Description |
|---|---|
| `policy_score` | Policy compliance (0-1) |
| `outcome_score` | Likelihood of desired outcome (0-1) |
| `risk_score` | Risk/exposure level (0-1, inverted) |
| `context_fit_score` | How well it matches context (0-1) |

**How it works:**
```python
def evaluate(options: list[PlanOption], weights: Weights) -> list[ScoredOption]:
    scored = []
    
    for opt in options:
        scores = {
            "policy_score": calc_policy_score(opt),
            "outcome_score": calc_outcome_score(opt),
            "risk_score": calc_risk_score(opt),
            "context_fit_score": calc_context_fit(opt)
        }
        
        total = sum(scores[k] * weights[k] for k in scores)
        scored.append(ScoredOption(option=opt, scores=scores, total=total))
    
    return sorted(scored, key=lambda x: x.total, reverse=True)
```

---

### 2.6 Decision Selector

**What it is:** Selects the highest-scoring option, writes DecisionRecord to `/verdict`.

**Key responsibilities:**
- Select best option
- Write decision record
- Log for audit

**Output (DecisionRecord):**
```json
{
  "decision_id": "dec_7f3a2b1c",
  "selected_plan": "plan_001",
  "timestamp": "2026-04-18T10:30:00Z",
  "scores": {
    "policy_score": 1.0,
    "outcome_score": 0.85,
    "risk_score": 0.9,
    "context_fit_score": 0.75,
    "weighted_total": 0.87
  },
  "all_options_considered": 5
}
```

**Write to `/verdict`:**
```python
def write_verdict(record: DecisionRecord):
    path = Path("/verdict") / f"{record.decision_id}.json"
    path.write_text(record.model_dump_json(indent=2))
```

---

## 3. Memory System

Four-layer memory architecture: Context Store → Vector Index → KV Cache → Episodic Store → Pattern Store.

### 3.1 Context Store (SQLite WAL)

**What it is:** Typed entity storage with SQLite WAL persistence.

**Key Responsibilities:**
- Store structured entities (Decision, Observation, Constraint, Relationship)
- ACID transactions via WAL mode
- Efficient querying by entity type

**Schema:**
```python
class EntityType(str, Enum):
    DECISION = "decision"
    OBSERVATION = "observation"
    CONSTRAINT = "constraint"
    RELATIONSHIP = "relationship"

def store_entity(entity: EntityType, data: dict):
    conn.execute(
        "INSERT INTO entities (type, data) VALUES (?, ?)",
        (entity.value, json.dumps(data))
    )
```

---

### 3.2 Vector Index (Chroma + nomic-embed-text)

**What it is:** Semantic retrieval for similar past decisions/workflows.

**Key responsibilities:**
- Embed text with nomic-embed-text model
- Store in Chroma collection
- Query by similarity

**How it works:**
```python
import chromadb
from chromadb.utils.embedding_functions

client = chromadb.Client()
ef = embedding_functions.NomicEmbeddingFunction()
collection = client.get_or_create_collection(
    "decisions",
    embedding_function=ef
)

def semantic_search(query: str, limit: int = 5) -> list[dict]:
    results = collection.query(
        query_texts=[query],
        n_results=limit
    )
    return parse_results(results)
```

---

### 3.3 KV Cache (Redis Unix Socket)

**What it is:** Session state and rate-limiting with Redis via Unix socket.

**Key responsibilities:**
- Store session state (TTL-based)
- Rate-limit API calls
- Fast lookups for hot data

**How it works:**
```python
import redis

r = redis.Redis(unix_socket="/var/run/redis.sock")

def get_session(session_id: str) -> dict:
    return json.loads(r.get(f"session:{session_id}"))

def rate_limit(key: str, limit: int = 100, window: int = 60) -> bool:
    current = r.incr(f"ratelimit:{key}")
    if current == 1:
        r.expire(f"ratelimit:{key}", window)
    return current <= limit
```

---

### 3.4 Episodic Store

**What it is:** Records every decision with outcome, prediction delta for learning.

**Key responsibilities:**
- Log decision → outcome pairs
- Calculate prediction error (actual vs. predicted)
- Feed learning loop

**Schema:**
```python
class Episode(BaseModel):
    decision_id: str
    intent: Intent
    selected_plan: PlanOption
    outcome: dict
    prediction_delta: float  # (outcome - predicted_confidence)
    timestamp: datetime
```

---

### 3.5 Pattern Store

**What it is:** Aggregates patterns: success rates, confidence, observation counts, context signatures.

**Key responsibilities:**
- Track statistics per pattern
- Update weights based on outcomes
- Feed evaluator for scoring

**Schema:**
```python
class Pattern(BaseModel):
    context_signature: str  # Hash of intent + context
    success_rate: float
    confidence: float
    observation_count: int
    avg_prediction_delta: float
```

---

## 4. Execution Flow (10 Steps)

The complete pipeline from input to result.

### Step 1: Input Ingestion

CLI/API → InboundEvent

```python
class InboundEvent(BaseModel):
    source: str  # "cli" or "api"
    raw_input: str
    session_id: str
    metadata: dict
```

---

### Step 2: Intent Parsing + Context Enrichment

```python
def parse_and_enrich(event: InboundEvent) -> Intent:
    intent = parse_intent(event.raw_input)
    intent = enrich_with_context(intent, memory)
    return intent
```

---

### Step 3: Load Context Manifest

Nexi loads context from memory:

```python
def load_context(intent: Intent, memory: Memory) -> ContextManifest:
    return ContextManifest(
        intent=intent,
        past_decisions=memory.semantic_search(intent.raw_input),
        constraints=memory.get_constraints(intent),
        session_state=memory.get_session(event.session_id)
    )
```

---

### Step 4: Generate Plan Options

Nexi → vLLM generates 3-7 options:

```python
options = generate_options(manifest, n=5)
```

---

### Step 5: Policy Filter

Check each option:

```python
options = filter_options(options)  # BLOCK/MODIFY/ALLOW
```

---

### Step 6: Evaluator + Decision Selector

Score and select:

```python
scored = evaluate(options, weights)
selected = pick_top(scored)
write_verdict(selected)
```

---

### Step 7: Execution Token

xnch issues token after `/verdict`:

```python
def issue_token(decision: DecisionRecord) -> ExecutionToken:
    if not Path("/verdict").exists():
        raise PermissionError("No verdict — cannot proceed")
    return ExecutionToken(decision_id=decision.decision_id)
```

---

### Step 8: Simulation + Diff Render

Mandatory human gate:

```python
def simulate_and_render(plan: PlanOption) -> SimulationResult:
    result = simulate(plan, context)
    console.print(result.diff)
    # Wait for human confirmation
```

---

### Step 9: Execution + Event Emission

Execute and emit to ledger:

```python
def execute_and_emit(plan: PlanOption, token: ExecutionToken):
    result = executor.run(plan)
    ledger.emit(DecisionEvent(
        decision_id=token.decision_id,
        outcome=result.model_dump()
    ))
```

---

### Step 10: Memory Write-back + Learning Loop

Update memory, update weights:

```python
def writeback_and_learn(decision: DecisionRecord, outcome: dict):
    # Write to episodic store
    memory.store_episode(Episode(
        decision_id=decision.decision_id,
        intent=decision.intent,
        selected_plan=decision.selected_plan,
        outcome=outcome,
        prediction_delta=abs(outcome["success"] - decision.confidence)
    ))
    
    # Update pattern weights
    pattern_store.update(decision.context_signature, outcome)
```

---

## Quick Reference

| Component | Role |
|---|---|
| **xnch** | Control plane: CLI → intent → execute |
| **Nexi** | Decision engine: interpret → generate → filter → score → select |
| **Context Store** | SQLite: typed entities |
| **Vector Index** | Chroma: semantic search |
| **KV Cache** | Redis: session + rate limits |
| **Episodic Store** | Decision → outcome logs |
| **Pattern Store** | Aggregated success patterns |

---

## Next Steps

- [API Reference](./api-reference.md)
- [Configuration Guide](./config.md)
- [Troubleshooting](./troubleshooting.md)