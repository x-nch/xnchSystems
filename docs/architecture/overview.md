# System Overview

---
tags:
  - #architecture
  - #reference
  - #xnch
---

xnch is not an AI assistant. It is a governed decision infrastructure — a control plane that separates the mechanics of reasoning from the act of deciding from the generation of content.

At its core, xnch imposes discipline on what is normally a chaotic, opaque, single-pass process in most AI systems: user input → model output. Instead, it interposes multiple bounded layers, each with a distinct contract:

- **xnch (control plane)** is the traffic authority. It owns routing, policy enforcement, access control, and audit trails. It never generates content. It governs what enters and exits the system.
- **Nexi (decision engine)** is the reasoning substrate. It evaluates context, applies decision logic, selects from available strategies, and orchestrates model calls. It selects decisions — it does not hallucinate them.
- **Model layer** is a generation substrate. It produces structured output on demand, called by Nexi with constrained prompts. Its output is fed back to Nexi for evaluation, not directly to the user.
- **Memory system** is a structured, queryable, evolving knowledge graph. It feeds Nexi, not models directly.
- **Execution layer** is the effector — it acts on the world only after the full reasoning + control cycle completes.

The canonical flow is a closed-loop governance circuit, not a pipeline:

```
User/Agent → xnch → Nexi → Model → Nexi → xnch → Execution → Memory Update
                ↑_______________________________________________|
```

---

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
│                      Control Plane (xnch)                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ Policy Engine│  │ Governance   │  │  Audit Logger        │  │
│  │              │  │ Layer (RBAC) │  │  (Append-only)       │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│                    Decision Engine (Nexi)                      │
│  Intent Interpreter → Option Generator → Policy Filter         │
│  → Evaluator → Outcome Simulator → Decision Selector           │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│                     Abstraction Layer                          │
│  ┌─────────────────────┐  ┌─────────────────────────────────┐  │
│  │    Model Adapter    │  │      Plan Compiler              │  │
│  │ (vLLM / llama.cpp)  │  │   (Steps → Execution)           │  │
│  └─────────────────────┘  └─────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│                      Memory Layer                              │
│  ┌───────────┐ ┌───────────┐ ┌─────────┐ ┌─────────────────┐  │
│  │ Context   │ │ Vector    │ │  KV     │ │   Episodic +    │  │
│  │ Store     │ │ Index     │ │ Cache   │ │   Pattern Store  │  │
│  │ (SQLite)  │ │(sqlite-vec│ │(Redis)  │ │   (SQLite)      │  │
│  └───────────┘ └───────────┘ └─────────┘ └─────────────────┘  │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│                       Audit Layer                              │
│  ┌───────────────┐ ┌─────────────────┐ ┌─────────────────┐    │
│  │  Event Log    │ │ Decision Ledger │ │  Replay Engine  │    │
│  │ (Append-only) │ │ (JSONL + SHA256)│ │                 │    │
│  └───────────────┘ └─────────────────┘ └─────────────────┘    │
└────────────────────────────────────────────────────────────────┘
```

---

## Cross-Cutting Concerns

| Concern | Implementation |
|---------|----------------|
| Error handling | Exception hierarchy, graceful degradation per component |
| Logging | structlog (JSON output) throughout all layers |
| Tracing | `trace_id` propagated via headers across all service calls |
| Metrics | Prometheus metrics per layer |
| Configuration | YAML-based, environment variable override |

---

For design principles and the rationale behind these boundaries, see [Principles](principles.md).
