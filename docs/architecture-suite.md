# Architecture Diagram Suite — SUPERSEDED

This single-file suite (no-k3s diagrams, Aug 2026) has been superseded by the
modular architecture docs. Content mapping:

| Old section | New home |
|---|---|
| §1 System Architecture | [overview](architecture/overview.md) |
| §2 Infrastructure | [topology](architecture/topology.md) |
| §3 xnch control plane | [overview](architecture/overview.md) + [api-xnch reference](reference/api-xnch.md) |
| §4 nexi pipeline | [decision-pipeline](architecture/decision-pipeline.md) |
| §5 Memory evolution (+§5a tier graph) | [memory](architecture/memory.md) |
| §6 Schema ERDs | [data-model](architecture/data-model.md) |
| §7 Read sequence | [decision-pipeline](architecture/decision-pipeline.md) + [memory](architecture/memory.md#recall-flow-read-side) |
| §8 Write sequence | [decision-pipeline](architecture/decision-pipeline.md) + [workflows-hitl](architecture/workflows-hitl.md) |

MCP bridge guide moved to [architecture/mcp-bridge](architecture/mcp-bridge.md).
Standalone diagram source: [`diagrams/mcp-bridge.mmd`](diagrams/mcp-bridge.mmd).
