# xnchSystems Architecture — Post-LangGraph Integration

## What changed vs. the original design

| Layer | Before | After LangGraph |
|---|---|---|
| Control | Custom sequential Intent Parser → Policy Gate → Sim Engine → Executor | `StateGraph` with typed state, conditional edges, `interrupt()` gates |
| Nexi | Parallel 5-stage pipeline (II→OG→PF→EV→DS) | Single subgraph node invoked by the orchestrator, same internal stages |
| Agents | Registry + Supervisor + Router (custom) | LangGraph supervisor pattern — fan-out to worker agent nodes |
| Persistence | Ad hoc, mostly Audit Layer only | `langgraph-checkpoint-postgres` checkpoints *every* state transition |
| Human gate | Implicit / app-level rule ("no auto kubectl apply") | Explicit `interrupt()` node before Executor on destructive ops |
| Memory | SQLite + Chroma + Redis KV cache | Redis sensory cache (60s TTL) → Redis working memory → pgvector episodic → Kuzu semantic graph |
| Observability | Audit log only | Langfuse traces on every node execution (LangSmith explicitly excluded — local-only constraint) |

## Diagram

```mermaid
flowchart TB
    subgraph INPUT["INPUT LAYER"]
        CLI["xnch CLI"]
        GW["REST/gRPC Gateway"]
        EB["Event Bus"]
    end

    subgraph ORCH["ORCHESTRATION LAYER — LangGraph StateGraph"]
        IP["parse_intent node"]
        NEXISUB["nexi_decide subgraph node<br/>(II → OG → PF → EV → DS internally)"]
        PG{"policy_gate<br/>conditional edge"}
        SE["simulate node"]
        HITL["🛑 interrupt()<br/>human approval gate<br/>(destructive ops only)"]
        EX["execute node"]
        CKPT[("Postgres Checkpointer<br/>langgraph-checkpoint-postgres<br/>— state history every transition")]
    end

    subgraph AGENTS["AGENTS LAYER — LangGraph Supervisor Pattern"]
        AS["Agent Supervisor node<br/>(fan-out)"]
        WA1["Worker Agent 1"]
        WA2["Worker Agent 2"]
        WAn["Worker Agent N"]
        TR["Tool Router<br/>conditional edge"]
        MA["Model Adapter<br/>→ LiteLLM → vLLM/Ornith-1.0-35B"]
    end

    subgraph MEMORY["MEMORY LAYER — Four-Tier"]
        SC["Sensory Cache<br/>Redis, 60s TTL"]
        WM["Working Memory<br/>Redis sliding window"]
        EM["Episodic Store<br/>pgvector, decay scoring"]
        SM["Semantic Graph<br/>Kuzu"]
    end

    subgraph AUDIT["AUDIT LAYER"]
        EL["Append-only Event Log"]
        DL["Decision Ledger"]
        RE["Replay Engine<br/>(replays from checkpointer state)"]
        LF["Langfuse traces<br/>(per-node observability)"]
    end

    subgraph LEARNING["LEARNING LAYER"]
        OC["Outcome Collector"]
        PE["Pattern Extractor"]
        SA["Score Adapter"]
        PC["Policy Candidate Gen"]
    end

    CLI --> GW --> EB --> IP
    IP --> NEXISUB
    NEXISUB --> PG
    PG -->|approve| SE
    PG -->|reject/replan| IP
    SE --> HITL
    HITL -->|approved| EX
    HITL -->|denied| IP
    EX --> AS
    AS --> WA1 & WA2 & WAn
    WA1 & WA2 & WAn --> TR --> MA

    IP -.checkpoint.-> CKPT
    NEXISUB -.checkpoint.-> CKPT
    PG -.checkpoint.-> CKPT
    HITL -.checkpoint.-> CKPT
    EX -.checkpoint.-> CKPT

    NEXISUB --> SC
    NEXISUB --> WM
    NEXISUB --> EM
    NEXISUB --> SM

    EX --> EL --> DL --> RE
    IP -.trace.-> LF
    EX -.trace.-> LF

    EX --> OC --> PE --> SA --> PC --> PG
```

## Interview talking points this diagram supports

1. **Why LangGraph over a custom orchestrator** — you already had a working hand-rolled Control Layer. The judgment call was: checkpointing, replay, and interrupt semantics are hard to get right and easy to get subtly wrong under failure; LangGraph gives you that for free while you keep full control of node logic. Good "build vs. adopt" story for FDE interviews.

2. **Checkpointer as durability, not just logging** — Postgres checkpoints mean a crashed run resumes from its last node, not from zero. Ties directly into your payments background: idempotency and exactly-once-ish semantics under partial failure is the same problem you solved with Kafka consumer offsets at Rakuten.

3. **`interrupt()` as the enforcement point for your no-auto-apply rule** — this is a stronger story than "we have a rule" — it's "the rule is structurally unbypassable because the graph literally cannot reach the execute node without a human resuming it." Concrete answer to "how do you prevent an agent from doing something destructive."

4. **Supervisor pattern in the Agents layer** — fan-out/fan-in with a router is the standard answer to "how would you architect a multi-agent system," and you can point at a running implementation instead of whiteboard theory.

5. **LangSmith exclusion** — good answer to "how do you handle observability without vendor lock-in / with a local-only constraint." Langfuse self-hosted + Postgres checkpoints as the audit trail is a defensible substitute.

6. **Known gaps, stated plainly** — Kuzu not fully wired into the write path, `PgEpisodicStore.connect()` still a stub. Naming these unprompted in an interview reads as engineering maturity, not weakness — you know exactly where the system is incomplete and why.
