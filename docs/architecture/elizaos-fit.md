# elizaOS: Architecture-Fit & Borrow-Backlog Analysis

Status: Informational (decision: **borrow, don't switch**)
Date: 2026-08-27
Scope: elizaos/eliza (TypeScript agent framework) vs nexi/xnch (Python control plane + policy engine)

## TL;DR

elizaOS and the nexi/xnch stack are **philosophically opposed** systems. nexi/xnch is a
policy-gated, human-in-the-loop, audited control plane; elizaOS is an autonomous,
personality-driven agent runtime. A framework switch would be a full rewrite with zero
architectural gain. The only borrowable assets are (1) a few concrete engineering patterns
and (2) elizaOS's 125-plugin catalog used as a **connector backlog roadmap**.

## Decision

- **Do NOT switch.** No incremental path exists: elizaOS is TypeScript/Bun; nexi/xnch is
  Python 3.13/FastAPI/LangGraph/Memgraph. Rewriting would discard 244+ passing tests,
  Pydantic models, the LangGraph HITL StateGraph, and the PolicyFilter bridge for no benefit.
- **Do NOT integrate elizaOS as a peer for the core.** Its autonomy self-loop
  (`plugin-blocker`/`autonomy`) erodes the governance moat (HITL `should_interrupt_execution`,
  policy verdicts, execution tokens).
- **Borrow at the pattern level only**, and only the two items in [What to borrow](#what-to-borrow).
- **Optional**: run elizaOS as a *separate, feature-flagged* service for personality-driven
  social bots that fan into xnch `PolicyFilter` — identical to the beeAI pattern already used.

## Architectural Incompatibility Matrix

| Dimension | nexi/xnch | elizaOS | Verdict |
|---|---|---|---|
| Core identity | Policy-governed decision engine | Autonomous agent runtime | Contradictory |
| Control model | Deterministic LangGraph DAG, HITL interrupts | Message loop (receive→decide→act→learn) | Conflict |
| Safety | PolicyFilter → verdict (ALLOW/BLOCK), risk-weighted eval | Approval boundaries on wallet ops only | elizaOS weaker |
| Stack | Python 3.13 / FastAPI / LangGraph / Memgraph | TypeScript / Bun | Rewrite |
| Memory | Hierarchical, policy-scoped, audited (pgvector/Memgraph) | RAG-for-personality (Knowledge plugin) | Different purpose |
| Deployment | 2-node bare-metal, 3090 RTX, systemd, local-first | Cloud + OS distros | Incompatible posture |

## What was already implemented during this analysis

Lifted elizaOS's `promptSegments {content, stable}` idea into the context assembler — the
one portable, language-agnostic perf win:

- `nexi/character/prompt_loader.py`
  - Added `PromptSegments(stable, dynamic)` dataclass and `build_prompt_segments()`.
  - Split the system prompt into a **stable prefix** (persona, identity, capabilities,
    rules) and a **dynamic suffix** (session memory, entities, timestamps).
  - Added `_STABLE_CACHE` keyed on a hash of the stable inputs; unchanged character config
    reuses the rendered preamble instead of re-parsing YAML on every assembly.
  - `build_system_prompt()` now delegates to `build_prompt_segments()` (backward compatible).
- `nexi/pipeline/context_assembler.py`
  - `AssembledContext` now carries `prompt_segments` alongside `system_prompt`.
  - `assemble_context()` builds via segments; `system_prompt == stable + dynamic`.

Measured effect: stable prefix ~5,097 chars (~1,300 tokens) frozen byte-identical across
calls; dynamic suffix ~82 chars. This is the shape providers want for prompt caching
(Anthropic `cache_control`, OpenAI/Gemini stable-prefix reordering). Tests:
`nexi/tests/test_prompt_loader.py`, `nexi/tests/test_context_assembler.py` (40 pass).

## What to borrow

### 1. Prompt batching + stable-prefix caching — DONE (above)

### 2. elizaOS plugin catalog as a connector backlog — SEE BELOW

## elizaOS 125-plugin catalog → nexi/xnch backlog

naming: elizaOS `plugin-*` entries, mapped to nexi/xnch priority. Gap finding: **nexi has
zero social/platform connectors today** (only `model_adapter` + `xnch_client` adapters), so
the catalog is a roadmap, not a dependency.

### Tier A — Build first (missing primitive, high leverage)

| elizaOS plugin | What it gives | nexi/xnch equivalent / gap |
|---|---|---|
| plugin-mcp | MCP server/client support | Already present (bridged `crg_*`, `am_*`, `doc_*` tools) — **already covered** |
| plugin-web-search | web search tool | Gap — no web-search tool in `tools` |
| plugin-browser / plugin-computeruse | browser automation | Gap — no browser surface |
| plugin-sql / plugin-embeddings | SQL + embedding utils | Partially covered (pgvector); SQL tool not exposed |
| plugin-pdf / plugin-documents / plugin-vision | file/vision ingestion | Gap for docs/multimodal |

### Tier B — Social connectors (persona agents only; feature-flag if ever wanted)

platform-x, platform-discord, platform-telegram, platform-slack, platform-whatsapp,
platform-matrix, platform-wechat, platform-instagram, platform-farcaster, platform-imessage,
plugin-phone. **Recommendation: skip for the core** — nexi is operator-facing/voice-first.
Only revisit behind the xnch `PolicyFilter` if personality-driven outreach becomes a goal.

### Tier C — Native device / OS bridges (mobile/desktop)

plugin-native-* family (camera, contacts, filesystem, location, screencapture,
secure-store, wifi, calendar, reminders, network-policy, phone, system, talkmode).
Not relevant to the 2-node bare-metal control plane. Skip.

### Tier D — Productivity / orchestration (assess, many already have analogues)

goals, tasks, todos, reminders, scheduling, calendar, notes, documents, workflow /
task-coordinator, relations, messages, inbox, feed. nexi/xnch already has a goals API,
workflow executor, sessions, memory. These validate the roadmap more than they add.

### Tier E — Blockchain / Web3 (wallet ecosystem)

plugin-wallet, plugin-wallet-ui, plugin-finances, plugin-taskmarket, plugin-social-alpha,
plugin-defense-of-the-agents. Skip — not in-scope for a privacy-first control plane
unless the operator opts into Web3 later.

### Tier F — Infra / storage internally

plugin-inmemorydb, plugin-local-storage, plugin-registry. nexi/xnch already has
pgvector/Memgraph/stores. Skip.

## Conclusion

elizaOS is a **roadmap generator** for nexi/xnch, not a runtime to adopt. The single
biggest real gap it exposes is the **absence of any social/web-tool connector layer**.
The prompt-segmentation pattern has already been lifted and shipped. Nothing in the
catalog justifies adopting the framework or its autonomy model.
