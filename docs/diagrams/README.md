# Architecture Diagrams

## Primary reference (no-k3s, Aug 2026)

| File | Description |
|------|-------------|
| **`architecture-suite.md`** | **Eight canonical diagrams: system architecture, infra, xnch, nexi, memory evolution, schema, read path, write path** |

## Legacy / component diagrams

| File | Description |
|------|-------------|
| `system-overview.mmd` | Historical k3s two-node layout (superseded by `architecture-suite.md` §1–2) |
| `memory-layers.mmd` | Four-tier memory tiers with write/retrieve paths |
| `request-lifecycle.mmd` | Chat request sequence (update model refs to Ornith when editing) |
| `trust-model.mmd` | Actor-based trust enforcement by JWT role |
| `learning-loop.mmd` | Pattern extraction, weight adaptation, policy candidates (6h cron) |
| `perception-pipeline.mmd` | Voice / vision / file perception → sensory buffer |
| `memory-evolution-loop.md` | Episode → pattern → weight feedback (high-level) |
| `nexi-decision-loop.md` | Nexi pipeline overview |
| `execution-flow.md` | Verdict → dispatch → outcome |
