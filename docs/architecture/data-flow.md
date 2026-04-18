# Data Flow

The 10-step execution flow through the xnch + Nexi system.

## Execution Steps

```
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│  Step 1 │────▶│  Step 2 │────▶│  Step 3 │────▶│  Step 4 │
│  Input  │     │ Intent  │     │ Context │     │ Option  │
│Ingestion│     │ Parsing │     │ Manifest│     │Generation│
└─────────┘     └─────────┘     └─────────┘     └─────────┘
                                                            │
       ┌────────────────────────────────────────────────────┘
       │
       ▼
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│  Step 5 │────▶│  Step 6 │────▶│  Step 7 │────▶│  Step 8 │
│ Policy  │     │ Evaluate│     │  Final  │     │Simulate │
│ Filter  │     │(4 dims) │     │ Verdict │     │  + Gate │
└─────────┘     └─────────┘     └─────────┘     └─────────┘
                                               │
       ┌───────────────────────────────────────┘
       │
       ▼
┌─────────┐     ┌─────────┐
│  Step 9 │────▶│ Step 10 │
│Execute  │     │ Memory  │
│          │     │Writeback│
└─────────┘     └─────────┘
```

## Step Details

### Step 1: Input Ingestion

User input received via CLI or API. Raw string prepared for parsing.

**Output**: Raw input string

**Components**: Typer CLI, FastAPI endpoint

### Step 2: Intent Parsing

Input converted to normalized Intent object with classified intent_class, action_type, and entity_class.

**Input**: Raw input string
**Output**: Intent object

**Components**: Intent Parser

### Step 3: Context Manifest Load

Current memory state loaded to inform option generation - recent contexts, relevant patterns, outcome history.

**Input**: Intent object
**Output**: Context Manifest

**Components**: Memory Layer (Context Store, Vector Index)

### Step 4: Option Generation

LLM generates N candidate plans from intent + context. Default N=5, configurable.

**Input**: Intent + Context Manifest
**Output**: List[Plan] (N candidates)

**Components**: Model Adapter, vLLM/Ollama

### Step 5: Policy Filter

Candidates filtered against defined policies. Removes plans violating safety, compliance, or operational rules.

**Input**: List[Plan]
**Output**: List[Plan] (filtered)

**Components**: Nexi Policy Filter

### Step 6: Evaluation

Remaining candidates evaluated across four dimensions: safety, efficiency, compliance, context_fit.

**Input**: List[Plan]
**Output**: List[EvaluatedPlan] with scores

**Components**: Nexi Evaluator

### Step 7: Final Verdict + Token

Highest-scoring plan selected as final decision. Unique decision token generated for audit trail.

**Input**: List[EvaluatedPlan]
**Output**: Selected Plan + Decision Token

**Components**: Nexi Decision Selector

### Step 8: Simulation + Human Gate

Plan simulated in sandbox mode. Human approval requested if threshold met.

**Input**: Selected Plan
**Output**: Approved Plan or rejected

**Components**: Simulation Engine, Human Gate

### Step 9: Execution

Approved plan executed with real side effects. Execution monitored and errors captured.

**Input**: Approved Plan
**Output**: Execution Result

**Components**: Plan Compiler, Execution Engine

### Step 10: Memory Write-back + Learning

Outcome recorded to Outcome Store. Learning Loop triggered to update patterns and scores.

**Input**: Execution Result
**Output**: Updated stores

**Components**: Memory Layer, Learning Loop