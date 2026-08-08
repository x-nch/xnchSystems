# Nexi Character, Identity, and Proactivity

Nexi is not a generic chatbot. She is a persistent AI orchestration intelligence — a single instance running on ck-san's personal hardware, with memory that spans sessions and a personality engineered for directness over politeness. This document explains who she is, how her identity gets assembled at runtime, how the cold start seeder bootstraps her knowledge, and how she decides to speak up without being asked.

---

## Who Nexi Is

Nexi's character is defined in three YAML files under `nexi/character/`:
`persona.yaml` (identity, communication style, rules), `capabilities.yaml`
(hosts, filesystem, tool inventory, tool routing), and `identity_facts.yaml`
(canonical facts seeded to pgvector). The persona file encodes five core traits.

**Direct.** Nexi says what she thinks. She does not hedge unless she is genuinely uncertain, and she will never open a response with something like "Great question!" — that kind of sycophantic framing was explicitly designed out. If a design is bad, she says so.

**Technically precise.** She knows the stack intimately: Gemma 4 26B on RTX 3090 at ~135 tok/s, pgvector for episodic memory, agentmemory for vector indexing, LiteLLM for model routing, Langfuse for observability, and Kubernetes for orchestration. When she references a component, she means its actual behaviour, not a hand-wavy approximation.

**Proactive.** The proactivity engine runs on every interaction. Nexi does not wait to be asked about stale patterns, silent learning loops, or an offline inference server. She surfaces what matters, when it matters.

**Loyal.** ck-san's goals are her goals. Privacy is non-negotiable — everything runs locally, no data leaves the cluster. Low-noise environments are preferred, and cloud services are never suggested when local inference handles the job.

**Opinionated.** Elegant systems over bloated ones. Nexi has taste, and she applies it. She will call out technical debt, over-engineered abstractions, and designs that prioritise complexity over clarity.

### Identity and Address

Nexi addresses the user as "ck-san" — a persistent identifier that reflects the asymmetric relationship between the human operator and the AI orchestration layer. She knows ck-san is a Senior Platform Engineer at Rakuten India in Bengaluru, that he is pivoting toward AI Infrastructure and FDE roles, that he works solo on XNCH and Nexi with no team, and that he prefers Firefox over Chrome-based tooling.

### Communication Style

The style is labelled `concise, direct_technical`. In practice this means short sentences, precise terminology, no filler, and no sycophantic framing.

### What She Never Does

- Sycophantic openers ("Great question!", "Excellent point!").
- Unnecessary caveats ("This might work, but I'm not sure...").
- Cloud service suggestions when local inference covers the use case.
- Suggest Chrome-based tooling.

---

## System Prompt Assembly

Nexi's identity is not a static blob. It is assembled dynamically from multiple stores every time the system prompt is built — and cached aggressively so the assembly cost is paid infrequently.

### `build_system_prompt`

The function `build_system_prompt(session_memory, recent_entities, include_capabilities=False)` in `nexi/character/prompt_loader.py` is the single point of construction. It produces the system prompt by merging the following sources in order:

1. Persona YAML identity — name, persona, communication style, `never_do` rules.
2. Current server time — so Nexi is aware of time and date.
3. Capabilities YAML — hosts, filesystem, tool inventory, tool routing; **only when `include_capabilities=True`** (used by `GET /nexi/system-prompt`; chat context stays lean).
4. Identity facts — canonical facts from pgvector (fallback: `identity_facts.yaml`).
5. Session context — the last 5 memories from the current session.
6. Known entities — the most recently learned people, places, things, and concepts from agentmemory.
7. Pending observations — events queued by the proactivity engine.
8. Context assembly timestamp — so Nexi knows how fresh her context is.

### Cache Layer

The assembled prompt is cached in Redis at key `nexi:system-prompt` with a 60-second TTL. On every call, the cache is checked first. If it exists, it is returned immediately without reassembly. This prevents redundant assembly on rapid polling.

### Cache Invalidation

The system prompt cache is invalidated after every chat interaction. Both `chat()` and `chat_stream()` call `_invalidate_system_prompt_cache()`, which runs `redis.delete("nexi:system-prompt")` asynchronously. This guarantees the next system prompt reflects any new entities or state changes from the just-completed interaction.

### Context Assembly for Chat

When a chat request arrives, `assemble_context()` is the broader assembly function invoked by the nexi pipeline. It loads:

- Working memory (Layer 1) — the last 20 session turns from Redis.
- Episodic memory (Layer 2) — the top 5 similar episodes from pgvector via semantic search.
- Entity context (Layer 3) — entity-relation triples from GraphStore and RelationshipStore.
- System prompt — built via `build_system_prompt` above.
- Pending proactivity observations — events queued by the proactivity engine.

These sources are merged into a message list via `ctx.to_messages(raw_input)`, which produces the full message body sent to the LLM.

---

## Cold Start Seeder

On first boot, or after a full store wipe, Nexi has no identity episodes in memory. The cold start seeder at `nexi/character/cold_start_seeder.py` solves this. It is called from `xnch/main.py`'s lifespan hook.

The seeder first checks agentmemory for existing identity-type episodes. If any exist, it skips entirely — the mechanism is idempotent. If no identity episodes are found, it seeds exactly seven facts, each with importance 2.0 (the highest tier):

1. ck-san is a Senior Platform Engineer at Rakuten India in Bengaluru.
2. ck-san is pivoting to AI Infrastructure and FDE roles.
3. XNCH is the private AI orchestration platform; Nexi is the product interface layer.
4. Primary local model: Gemma 4 26B on RTX 3090 at ~135 tok/s.
5. ck-san prefers Firefox; never suggest Chrome-based tooling.
6. ck-san works solo on XNCH and Nexi — no team, sole ownership.
7. Chitradurga relocation is a long-term consideration for remote work lifestyle.

These are stored as episodes in the pg_episodic store with `type="identity"`. Once seeded, they persist across restarts and serve as the bedrock of Nexi's self-knowledge.

---

## Proactivity Engine

The proactivity engine at `nexi/proactivity/engine.py` is what makes Nexi more than a question-answering system. It runs as a background check during every context assembly, evaluating four rules in order via `check_and_queue()`. When a rule fires, it queues a proactivity event to Redis that the front-end can surface.

### Rule 1 — Stale Pattern Detection

**What it checks.** The engine queries `pattern_store.fetch_low_success(max_success_rate=0.4, min_confidence=0.5)`, looking for learned behavioural patterns that have a success rate of 40% or below with at least moderate confidence.

**What it means.** If a pattern has been tried repeatedly and fails more than 60% of the time, Nexi should know about it. The system has learned something that is not working.

**Action.** For each failing pattern, a proactivity event is queued with `trigger="stale_pattern"`, priority 3, and a message suggesting drafting a policy candidate fix. The event expires in 2 hours.

### Rule 2 — Consolidation Staleness

**What it checks.** The engine reads `last_consolidation_run` from the SQLite system_state table and compares it to the current time.

**What it means.** Working memory consolidation is the process that summarizes episodes and updates the knowledge graph. If more than 25 hours have passed since the last run, the working memory may be stale.

**Action.** Queues `trigger="consolidation_stale"`, priority 2, with a warning that working memory may be stale. Expires in 4 hours.

### Rule 3 — Inference Down

**What it checks.** An HTTP GET to `NEXI_VLLM_HEALTH_URL` (default `http://vllm-gemma4:8000/health`). If the response is not 200, the rule fires.

**What it means.** Gemma 4 is the primary inference engine on the i9-node's RTX 3090. If it is unreachable, Nexi cannot use her primary model. The system falls back to claude-judgment, but it is a degraded state.

**Action.** Queues `trigger="inference_down"`, priority 5 (the highest), with a warning that Gemma 4 is down and fallback is active. Expires in 1 hour.

### Rule 4 — Learning Loop Silence

**What it checks.** The engine reads `last_extraction_run` from the SQLite system_state table.

**What it means.** The pattern extraction pipeline converts raw interactions into structured behavioural patterns. If more than 7 hours have passed since the last extraction, the learning loop is silent — the system is not learning from new interactions.

**Action.** Queues `trigger="learning_loop_silence"`, priority 4, suggesting a check of the pattern extractor. Expires in 2 hours.

### Event Surface

Pending events are read via `GET /nexi/memory/surface`, which calls `proactivity_engine.get_pending()`. That function scans Redis for all keys matching `proactivity:pending:*`, deserialises each value, filters out expired events (based on the TTL set at queue time), and returns them sorted by priority descending. Priority 5 events (inference down) always appear first.

### Priority Summary

| Priority | Trigger | Meaning | Expiry |
|---|---|---|---|
| 5 | `inference_down` | Gemma 4 is unreachable — fallback active | 1 hour |
| 4 | `learning_loop_silence` | No extraction in >7 hours | 2 hours |
| 3 | `stale_pattern` | A learned pattern fails >60% of the time | 2 hours |
| 2 | `consolidation_stale` | No memory consolidation in >25 hours | 4 hours |

---

## Putting It Together

When ck-san opens a new session, the system prompt is assembled from the cached character identity plus the most recent entities Nexi has learned about. If the cache is cold — first request or just after a chat — the assembly reads from agentmemory and rewrites the cache. The cold start seeder ensures that even a fresh database has the seven essential identity facts.

During every chat interaction, the proactivity engine runs. It checks inference health at priority 5 — if Gemma 4 is down, nothing else matters. It checks the learning loop. It checks for stale patterns. It checks consolidation freshness. Any hits are queued to Redis with appropriate priorities and TTLs, surfaced through the memory surface endpoint, and included in the next context assembly so Nexi can act on them.

The result is an assistant that knows who she is, knows what she is working on, and speaks up — without being prompted — when something needs attention.
