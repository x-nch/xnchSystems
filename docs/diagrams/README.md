# Architecture Diagrams

| File | Description |
|------|-------------|
| `system-overview.mmd` | Two-node k3s cluster layout showing i7 (memory) and i9 (inference) node services and communication paths |
| `memory-layers.mmd` | Four-tier memory architecture from Redis sensory buffer (L0) through working memory (L1), episodic store (L2), and graph store (L3) with write and retrieve paths |
| `request-lifecycle.mmd` | Full sequence of a chat request: user input through injection guard, context assembly, model routing via LiteLLM to Gemma 4, and response storage |
| `trust-model.mmd` | Actor-based trust enforcement flow mapping JWT roles (SYSTEM, OWNER, TRUSTED_AGENT, EXTERNAL, UNTRUSTED) to access levels with injection guard always active |
| `learning-loop.mmd` | Three 6-hour automated cycles (pattern extraction, weight adaptation, policy candidate generation) plus nightly consolidation with Zep summarization and Kuzu graph extraction |
| `perception-pipeline.mmd` | Three multi-modal input pipelines (voice via Silero VAD + whisper, vision via Moondream2, file via watchdog) converging into a 4-rule attention filter |
