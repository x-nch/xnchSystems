# Architectural Principles

---
tags:
  - #architecture
  - #component
  - #policy
---

These are the load-bearing decisions of the system. Violating any one of them collapses the design intent.

---

## Boundaries

### Boundary 1: xnch ↔ Nexi — Control vs. Reasoning

xnch does not reason. Nexi does not control. xnch enforces what is permitted; Nexi determines what is best within what is permitted.

If these collapse into each other — which happens in naive agent systems — you get policy bypass through reasoning, or reasoning paralysis through over-enforcement. They must be independently deployable, independently testable, and communicate only over the defined verdict/session contract.

### Boundary 2: Nexi ↔ Model Layer — Decision vs. Generation

In almost every production AI system, the model is the decision engine. xnch explicitly rejects this.

Nexi calls the model as a subroutine — not as an oracle. The model cannot escalate, cannot self-direct, cannot persist state. Nexi receives model output and applies deterministic evaluation logic before anything proceeds. This boundary is what makes the system auditable and reproducible. The model is an untrusted generator with a constrained output contract, treated the way a compiler treats user input: validated before any further processing.

### Boundary 3: Execution Layer ↔ Everything Else — Effect Isolation

No layer above the execution layer touches the real world. xnch doesn't execute. Nexi doesn't execute. Models definitely don't execute.

The execution layer receives a fully-formed, approved, audited action specification — carried in a signed execution token — and carries it out. Decision is decoupled from effect. If a component is compromised, it cannot cause real-world side effects without a valid token.

### Boundary 4: Memory System ↔ Model Layer — Structured State vs. Context Window

Memory does not flow directly into models as raw context. It flows into Nexi, which decides what to surface, how to frame it, and what to withhold.

This prevents model context pollution and ensures memory retrieval is a deliberate, governed act — not a dump of logs into a prompt. The model never sees the full system state. It sees only what Nexi judges relevant.

### Boundary 5: Post-Execution Memory Update — Feedback Loop Closure

Memory is updated after execution, not after generation.

The system learns from what happened in the world, not from what the model said. If memory were updated after model generation, the feedback signal would be circular — the system would learn what the model predicted, not what reality returned. Keeping the memory update post-execution ensures the loop trains on observed outcomes.

---

## Why Separation of Concerns is Non-Negotiable

Most AI systems fail in production for one of three reasons: unauditable decisions, uncontrolled side effects, or state drift. xnch's SoC directly addresses all three.

**Auditability** requires a single source of decision authority. If reasoning and control are colocated, you cannot reconstruct why a decision was made versus why it was permitted. In a compliance-sensitive context, that distinction is legally and operationally material. Nexi's decision log and xnch's control log must be independently queryable and must tell a coherent causal story together.

**Determinism** requires isolation from probabilistic components. The model layer is inherently non-deterministic. By quarantining it behind Nexi — which applies deterministic selection logic — the system's observable behavior becomes reproducible even when the underlying generation varies. This is the difference between a system you can test and a system you can only observe.

**Grounded feedback loops** require clean signal. If memory is contaminated by model output rather than grounded in execution outcomes, the system learns what the model predicted, not what the world returned. The loop corrupts itself over time. Keeping memory updates post-execution breaks the circularity.

**Policy enforceability** requires a chokepoint. You cannot enforce a policy that is distributed across layers. xnch is the single enforcement point. Policies defined there apply regardless of what Nexi decides, what the model generates, or what the execution layer is capable of. This is the architectural analog of a kernel boundary.

**Independent evolution** requires clean interfaces. Nexi's reasoning strategies can be upgraded without touching xnch's policy engine. The model layer can be swapped without changing decision logic. Memory schema can evolve without breaking execution contracts. Without explicit boundaries, changes in one component propagate unpredictably across the system.

---

## System Classification

xnch is architected the way a payment clearing system or air traffic control system is architected — not the way most AI products are.

Every decision in the system has:
- An **owner** (the component that made it)
- A **boundary** (the interface it cannot cross without evaluation)
- An **audit trail** (a record that is consistent with the verdict stream)
- A **feedback path** (outcome-grounded, not prediction-grounded)

That is not over-engineering. That is the minimum viable architecture for a system expected to improve over time without becoming unpredictable.
