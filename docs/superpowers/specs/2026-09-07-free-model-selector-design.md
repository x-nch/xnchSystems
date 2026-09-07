# Free Model Selector — Design Spec

## Overview

A two-component system for discovering, benchmarking, and selecting the best free LLM models from OpenCode Go and OpenRouter, with vLLM Ornith as default and free models as fallback.

**Components:**
1. `scripts/model_selector.py` — standalone CLI for discovery, probing, and ranking
2. `nexi/adapters/model_selector.py` — runtime module that reads rankings from Redis

## Goals

- Automatically discover available free models from OpenCode Go and OpenRouter
- Rank models by frontier quality (LMSYS ELO + manual tiers), latency (real probes), and cost (free)
- Cache rankings in Redis for fast runtime selection
- Dump JSON audit trail on each CLI run
- Integrate into `model_router.resolve()` as a ranking layer

## Non-Goals

- Paid model selection (only free-tier models)
- Token-level cost accounting (static `cost_tier` remains for paid models)
- Real-time streaming latency (only time-to-first-token measured)

---

## Component 1: CLI — `scripts/model_selector.py`

### Responsibilities

1. **Discover** — query OpenCode Go `/models` and OpenRouter `/models` for available free models
2. **Enrich** — pull LMSYS ELO scores, apply manual quality tiers from config
3. **Probe** — send a fixed test prompt to each model, measure time-to-first-token (TTFT) and total latency
4. **Rank** — composite score: `quality_score * 0.5 + (1 - normalized_latency) * 0.3 + context_score * 0.2`
5. **Store** — write rankings to Redis + dump JSON audit snapshot

### Discovery Sources

| Source | Endpoint | Free Filter |
|--------|----------|-------------|
| OpenCode Go | `GET /models` (auth'd) | All returned models (subscription = free) |
| OpenRouter | `GET https://openrouter.ai/api/v1/models` | Filter: `pricing.prompt == "0"` or model_id ends with `:free` |

### ELO Sources

| Source | Method | Notes |
|--------|--------|-------|
| LMSYS Chatbot Arena | `https://huggingface.co/api/datasets/lmsys/chatbot-arena-leaderboard` or cached JSON | ELO scores by model name; fuzzy match to OpenRouter model IDs |
| Manual tiers | `config/model_selector.yaml` | Override/fallback when ELO unavailable; tiers: `frontier`, `strong`, `mid`, `weak` |

### Latency Probing

- Fixed test prompt: `"Say hello in one sentence."` (minimal, fast)
- Measure: TTFT (time to first token) and total response time
- Run 3 probes per model, take median
- Timeout: 10s per probe
- Write results to Redis key `model_selector:latency:{provider}:{model_id}`

### Ranking Formula

```python
score = (
    quality_weight * quality_score        # 0-1, from ELO or manual tier
    + latency_weight * (1 - norm_latency) # 0-1, lower latency = higher score
    + context_weight * context_score      # 0-1, larger context = higher score
)
```

Default weights: `quality=0.5, latency=0.3, context=0.2`

Configurable via `config/model_selector.yaml`.

### Redis Schema

```
model_selector:rankings                  → LIST  sorted by score desc (JSON objects)
model_selector:meta:{provider}:{model}   → HASH  {context_window, cost_tier, elo, tier, strengths}
model_selector:latency:{provider}:{model}→ HASH  {ttft_ms, total_ms, probed_at}
model_selector:last_run                  → STRING ISO timestamp
model_selector:config                    → HASH  {weights, probe_prompt, timeout_s}
```

### Audit Trail

Dump to `data/model-rankings.json` on each run:
```json
{
  "run_at": "2026-09-07T12:00:00Z",
  "rankings": [...],
  "probes": {...},
  "elo_source": "lmsys",
  "models_discovered": 42,
  "models_ranked": 38
}
```

### CLI Interface

```bash
# Full run: discover + probe + rank + store
python scripts/model_selector.py run

# Probe only (skip discovery, re-benchmark known models)
python scripts/model_selector.py probe

# Show current rankings
python scripts/model_selector.py show

# Show rankings for a specific intent
python scripts/model_selector.py show --intent DECISION

# Force re-embed (after config change)
python scripts/model_selector.py run --force
```

### Config File — `config/model_selector.yaml`

```yaml
weights:
  quality: 0.5
  latency: 0.3
  context: 0.2

probe:
  prompt: "Say hello in one sentence."
  timeout_s: 10
  runs_per_model: 3

quality_tiers:
  frontier: 1.0
  strong: 0.75
  mid: 0.5
  weak: 0.25

manual_tiers:
  "anthropic/claude-sonnet-4": frontier
  "openai/gpt-4o": frontier
  "google/gemini-2.0-flash-001": strong
  "deepseek/deepseek-v4-pro": frontier
  "deepseek/deepseek-v4-lite": mid
  "nvidia/nemotron-3-super-120b-a12b:free": mid

redis:
  url: "redis://localhost:6379/0"
  ttl_s: 86400  # 24h
```

---

## Component 2: Runtime Module — `nexi/adapters/model_selector.py`

### Responsibilities

1. **Read** rankings from Redis at resolve-time
2. **Select** best model for given intent + budget
3. **Fallback** to static `ModelSpec` catalog if Redis is empty
4. **Expose** `get_best_model(intent, budget, exclude_providers)` and `get_ranked_models(intent)`

### Interface

```python
class ModelSelector:
    """Reads rankings from Redis, selects best free model."""

    async def get_best_model(
        self,
        intent: str,            # DECISION, EXECUTION, QUERY, ESCALATION
        budget: str = "balanced",
        exclude: list[str] | None = None,  # exclude providers/models
    ) -> ModelSpec | None:
        """Return best free model for intent, or None if no free model qualifies."""

    async def get_ranked_models(
        self,
        intent: str,
        limit: int = 5,
    ) -> list[ModelSpec]:
        """Return top N free models ranked for intent."""

    async def is_available(self) -> bool:
        """Check if rankings exist in Redis and are fresh (<24h)."""
```

### Integration Point — `model_router.py`

In `resolve()`, after trying the configured provider chain, add a **free-model ranked fallback**:

```python
# Current flow:
# 1. explicit model_id → use verbatim
# 2. nexi-default → litellm (if proxy set) → nexi_default_resolves_to
# 3. within provider: fallback_chain
# 4. cross-provider: chat_completion_with_fallback → openrouter free

# New flow (insert at step 4):
# 4. model_selector.get_best_model(intent, budget, exclude=[current_provider])
# 5. if selector returns a model → use it
# 6. else → openrouter free fallback (existing)
```

This means the selector is tried **before** the blunt openrouter free fallback, giving a smarter, latency-aware selection.

### Fallback Behavior

| Condition | Action |
|-----------|--------|
| Redis empty or stale (>24h) | Use static `ModelSpec` catalog (existing behavior) |
| Redis unavailable | Log warning, fall through to static catalog |
| All free models excluded | Return `None`, let existing fallback handle |
| Probe data missing for a model | Use ELO + tier score only (no latency component) |

---

## Integration into Nexi (Phase 2 — separate plan)

After the selector is working standalone:

1. Add `ModelSelector` singleton to `nexi/adapters/__init__.py`
2. Wire into `model_router.resolve()` as shown above
3. Add `/system/model-rankings` endpoint to xnch for visibility
4. Add systemd timer for CLI: `model-selector.timer` runs `model_selector.py run` hourly
5. Add Prometheus metric: `nexi_model_selector_score` per model

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `scripts/model_selector.py` | **CREATE** | CLI entrypoint |
| `nexi/adapters/model_selector.py` | **CREATE** | Runtime module |
| `config/model_selector.yaml` | **CREATE** | Config file |
| `nexi/config.py` | **MODIFY** | Add `model_selector_*` settings |
| `nexi/adapters/model_router.py` | **MODIFY** | Add selector fallback in `resolve()` |
| `data/` | **CREATE DIR** | Audit trail JSON output |

## Testing

- Unit tests for ranking formula, Redis read/write, fallback logic
- Mock Redis for unit tests, real Redis for integration tests
- CLI test: `python scripts/model_selector.py show` returns cached rankings
- Probe test: mock OpenCode Go / OpenRouter responses
- Integration test: `model_router.resolve()` picks selector model when Redis is populated

## Dependencies

- `redis` (already in stack)
- `httpx` (already in stack)
- `pyyaml` (already in stack)
- `pydantic` (already in stack)
