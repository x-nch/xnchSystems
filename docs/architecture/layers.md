# Layered Architecture

Component layers and their relationships.

## Layer Diagram

```
┌────────────────────────────────────────────────────────────────┐
│                     Presentation Layer                         │
│  ┌─────────────────────┐  ┌─────────────────────────────────┐  │
│  │    xnch CLI         │  │      FastAPI Server             │  │
│  │   (Typer + Rich)    │  │     (Uvicorn + Pydantic)        │  │
│  └─────────────────────┘  └─────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│                    Orchestration Layer                         │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │                   Nexi Engine                             │ │
│  │  Intent Interpreter → Option Generator → Policy Filter   │ │
│  │  → Evaluator → Decision Selector                         │ │
│  └──────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│                     Abstraction Layer                          │
│  ┌─────────────────────┐  ┌─────────────────────────────────┐  │
│  │    Model Adapter    │  │      Plan Compiler              │  │
│  │ (vLLM/Ollama/GPT)   │  │   (Steps → Execution)           │  │
│  └─────────────────────┘  └─────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│                      Storage Layer                             │
│  ┌───────────┐ ┌───────────┐ ┌─────────┐ ┌─────────────────┐  │
│  │ Context   │ │ Vector    │ │  KV     │ │   Outcome       │  │
│  │ Store     │ │ Index     │ │ Cache   │ │   Store         │  │
│  │ (SQLite)  │ │(ChromaDB) │ │(Redis) │ │   (SQLite)      │  │
│  └───────────┘ └───────────┘ └─────────┘ └─────────────────┘  │
│  ┌───────────┐ ┌───────────┐                                  │
│  │ Pattern   │ │ Episodic  │                                  │
│  │ Store     │ │ Store     │                                  │
│  └───────────┘ └───────────┘                                  │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│                       Audit Layer                              │
│  ┌───────────────┐ ┌─────────────────┐ ┌─────────────────┐  │
│  │  Event Log    │ │ Decision Ledger │ │  Replay Engine  │  │
│  │ (Append-only) │ │ (JSONL + SHA256) │ │                 │  │
│  └───────────────┘ └─────────────────┘ └─────────────────┘  │
└────────────────────────────────────────────────────────────────┘
```

## Layer Responsibilities

### Presentation Layer

- Human interaction via CLI (Typer + Rich) or API (FastAPI)
- Input validation and formatting
- Output rendering and formatting

### Orchestration Layer

- Nexi Engine coordinates decision-making
- Intent interpretation to final verdict
- Policy enforcement and evaluation

### Abstraction Layer

- Model Adapter provides LLM provider abstraction
- Plan Compiler converts plans to executable steps
- Enables swapping LLM backends without changing orchestration

### Storage Layer

- Context Store: SQLite with WAL for working memory
- Vector Index: ChromaDB for semantic search
- KV Cache: Redis for fast lookups
- Outcome Store: Historical execution records
- Pattern Store: Learned heuristics
- Episodic Store: Individual learning episodes

### Audit Layer

- Event Log: Append-only event record
- Decision Ledger: JSONL with SHA-256 chain for verification
- Replay Engine: Debugging and audit capabilities

## Cross-Cutting Concerns

| Concern | Implementation |
|---------|-----------------|
| Error Handling | Exception hierarchy, graceful degradation |
| Logging | Structured logging throughout all layers |
| Metrics | Prometheus metrics per layer |
| Tracing | OpenTelemetry spans for debugging |
| Configuration | YAML-based, environment variable override |