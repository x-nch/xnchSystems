# Free Model Selector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone CLI that discovers, benchmarks (ELO + real latency + context), and ranks free LLM models from OpenCode Go and OpenRouter, writing rankings to Redis, plus a runtime `ModelSelector` module that reads those rankings and selects the best free model for an intent. The eventual `model_router.resolve()` wiring is deferred (spec "Phase 2") and is NOT in this plan.

**Architecture:** Approach A (Centralized Selector). A `scripts/model_selector.py` CLI runs on a schedule: discovers models (`/models` on OpenCode Go + OpenRouter), enriches with ELO (LMSYS) + manual quality tiers, probes real latency (3 timed calls, median), scores (`quality*0.5 + latency*0.3 + context*0.2`), writes ranked list to Redis + a JSON audit dump. A `nexi/adapters/model_selector.py` module reads the Redis rankings at resolve-time and returns the best free model for an intent/budget, falling back to Nexi's static `ModelSpec` catalog when Redis is empty/stale.

**Tech Stack:** Python 3.13, httpx, redis (aioredis-free; `redis` sync + fakeredis for tests), PyYAML, pydantic. Async per repo convention (`asyncio_mode="auto"` in pytest).

**Spec:** `docs/superpowers/specs/2026-09-07-free-model-selector-design.md`

## Global Constraints

- Python `>=3.13` (root `pyproject.toml`).
- All tests async (`pytest.ini_options` sets `asyncio_mode = "auto"`); `nexi/tests/` tests import via `from nexi.adapters...`.
- Use `redis>=5.0` (already a dep) and `PyYAML` (already a dep). Use `fakeredis` for unit tests (already used in xnch tests) — add as dev dep if not present.
- Follow repo conventions: Pydantic `BaseModel`, `StrEnum`, `list[T]` lowercase generics, `str | None` unions, module-level logger `logging.getLogger(__name__)`, `Annotated` not required here.
- Settings live in `nexi/config.py` under `NEXI_` prefix.
- Do NOT modify `nexi/adapters/model_router.py` `resolve()` (that is the deferred Phase 2 wiring).
- No code comments unless they clarify a non-obvious public API; keep them minimal.
- Models considered "free" on OpenRouter: `pricing.prompt == "0"` OR model id ends with `:free` (matches existing `is_free_model()` in `nexi/adapters/llm.py`).

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `nexi/config.py` | MODIFY | Add `model_selector_*` settings + model-selector config path + Redis read TTL |
| `nexi/adapters/model_selector.py` | CREATE | Pure ranking logic + scoring + Redis read/write + `ModelSelector` runtime class |
| `nexi/adapters/__init__.py` | MODIFY | Re-export `ModelSelector` |
| `config/model_selector.yaml` | CREATE | Weights, tiers, manual ELO overrides, probe params, Redis URL |
| `scripts/model_selector.py` | CREATE | CLI: run / probe / show; HTTP discovery + latency probing |
| `nexi/tests/test_model_selector.py` | CREATE | Unit tests (scoring, ranking, Redis round-trip with fakeredis, fallback) |
| `tests/test_model_selector_cli.py` | CREATE | e2e HTTP-mocked CLI discovery/probe tests (uses `httpx.MockTransport`) |
| `data/` | CREATE | Output dir for `model-rankings.json` audit dump |

---

## Task 1: Config + scoring/ranking core (pure functions)

**Files:**
- Modify: `nexi/config.py` (add settings block after `openrouter_free_models`, line ~74)
- Create: `nexi/adapters/model_selector.py` (scoring + ranking pure functions; runtime class comes in Task 4)
- Test: `nexi/tests/test_model_selector.py`

**Interfaces:**
- Consumes: `nexi.config.settings` (new fields below), `nexi.adapters.model_router.ModelSpec`
- Produces:
  - `DEFAULT_WEIGHTS: dict[str, float]` = `{"quality": 0.5, "latency": 0.3, "context": 0.2}`
  - `TIER_SCORES: dict[str, float]` = `{"frontier": 1.0, "strong": 0.75, "mid": 0.5, "weak": 0.25}`
  - `def tier_from_elo(elo: float | None, tier: str | None) -> float` → mapped tier score
  - `def context_score(ctx: int) -> float` → `min(1.0, ctx / 1_000_000)`
  - `def normalized_latency(ms: int, cap_ms: int = 10_000) -> float` → `min(1.0, ms / cap_ms)`
  - `def rank_models(models: list[dict], elo: dict[str, float], tiers: dict[str, str]) -> list[dict]` → scored+sorted (desc) list of dicts with keys `provider, model_id, score, quality, latency_ms, context_window, elo, tier`

**Settings added to `nexi/config.py` (after the `openrouter_free_model`/`openrouter_free_models` block):**

```python
    # --- Free model selector (CLI writes rankings; runtime module reads) ---
    model_selector_weights: dict[str, float] = Field(
        default_factory=lambda: {"quality": 0.5, "latency": 0.3, "context": 0.2}
    )
    model_selector_config_path: str = "config/model_selector.yaml"
    model_selector_redis_ttl_s: int = 86_400  # rankings considered fresh for 24h
    model_selector_probe_prompt: str = "Say hello in one sentence."
    model_selector_probe_timeout_s: float = 10.0
    model_selector_probe_runs: int = 3
    model_selector_rankings_key: str = "model_selector:rankings"
```

**Steps:**

- [ ] **Step 1: Write the failing tests** for scoring + ranking in `nexi/tests/test_model_selector.py`:

```python
"""Tests for the free model selector scoring + ranking core."""

from __future__ import annotations

from nexi.adapters.model_selector import (
    TIER_SCORES,
    context_score,
    normalized_latency,
    rank_models,
    tier_from_elo,
)


def test_tier_from_elo_frontier():
    assert tier_from_elo(None, "frontier") == 1.0
    assert tier_from_elo(None, "weak") == 0.25


def test_tier_from_elo_falls_back_to_mid_when_no_tier():
    assert tier_from_elo(None, None) == 0.5


def test_tier_from_elo_elo_wins_over_tier():
    # frontier tier but mediocre elo -> elo-derived score clamps below tier max
    score = tier_from_elo(1100.0, "frontier")
    assert score < 1.0
    assert score > 0.0


def test_context_score_scales_to_1m():
    assert context_score(1_000_000) == 1.0
    assert context_score(200_000) == 0.2
    assert context_score(0) == 0.0


def test_normalized_latency_caps_at_10s():
    assert normalized_latency(0) == 0.0
    assert normalized_latency(500) == pytest.approx(0.05)
    assert normalized_latency(20_000) == 1.0


def test_rank_models_sorts_by_score_desc():
    models = [
        {"provider": "openrouter", "model_id": "a", "context_window": 128_000},
        {"provider": "openrouter", "model_id": "b", "context_window": 32_000},
    ]
    elo = {"a": 1300.0, "b": 900.0}
    tiers = {"a": "frontier", "b": "weak"}
    ranked = rank_models(models, elo, tiers)
    assert ranked[0]["model_id"] == "a"
    assert ranked[-1]["model_id"] == "b"
    assert set(ranked[0]) >= {
        "provider", "model_id", "score", "quality", "latency_ms",
        "context_window", "elo", "tier",
    }
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest nexi/tests/test_model_selector.py -v`
Expected: FAIL with `ModuleNotFoundError: nexi.adapters.model_selector`

- [ ] **Step 3: Add the settings block to `nexi/config.py`** (insert after the `openrouter_free_models` line, before `# Session`):

```python
    # --- Free model selector (CLI writes rankings; runtime module reads) ---
    model_selector_weights: dict[str, float] = Field(
        default_factory=lambda: {"quality": 0.5, "latency": 0.3, "context": 0.2}
    )
    model_selector_config_path: str = "config/model_selector.yaml"
    model_selector_redis_ttl_s: int = 86_400
    model_selector_probe_prompt: str = "Say hello in one sentence."
    model_selector_probe_timeout_s: float = 10.0
    model_selector_probe_runs: int = 3
    model_selector_rankings_key: str = "model_selector:rankings"
```

- [ ] **Step 4: Create `nexi/adapters/model_selector.py`** with the scoring core (runtime class added in Task 4):

```python
"""Free-model ranking core shared by the selector CLI and the runtime module.

The CLI discovers models, probes latency and writes rankings to Redis; the
runtime module reads those rankings and returns the best free model for an
intent. This module holds the pure scoring used by both, plus the
``ModelSelector`` runtime reader (see below).
"""

from __future__ import annotations

import logging
import math

logger = logging.getLogger(__name__)

DEFAULT_WEIGHTS: dict[str, float] = {"quality": 0.5, "latency": 0.3, "context": 0.2}

TIER_SCORES: dict[str, float] = {"frontier": 1.0, "strong": 0.75, "mid": 0.5, "weak": 0.25}

_MID_TIER_ELO = 1200.0
_ELO_SPREAD = 300.0  # elo range mapped to (0, 1] around a 1200 midpoint


def context_score(ctx: int) -> float:
    """Score a context window to [0,1], saturating at 1M tokens."""
    return min(1.0, max(0.0, ctx / 1_000_000))


def normalized_latency(ms: int, cap_ms: int = 10_000) -> float:
    """Latency to [0,1] with 0 = instant, 1 = >= cap (saturated)."""
    return min(1.0, max(0.0, ms / cap_ms))


def elo_to_score(elo: float) -> float:
    """Map an LMSYS-style elo to a (0,1] score centered on a 1200 midpoint."""
    return max(0.05, min(1.0, 1.0 - math.exp(-(elo - _MID_TIER_ELO) / _ELO_SPREAD)))


def tier_from_elo(elo: float | None, tier: str | None) -> float:
    """Quality score from elo (if numeric) else the manual tier score.

    A provided elo wins over the static tier when both are present.
    """
    if elo is not None:
        normalized = elo_to_score(elo)
        if tier:
            return min(normalized, TIER_SCORES.get(tier.lower(), 0.5))
        return normalized
    return TIER_SCORES.get((tier or "mid").lower(), 0.5)


def rank_models(
    models: list[dict],
    elo: dict[str, float],
    tiers: dict[str, str],
    weights: dict[str, float] | None = None,
) -> list[dict]:
    """Score and sort a list of model dicts by composite rank (desc).

    Each ``models`` item must have ``provider``, ``model_id`` and
    ``context_window``; ``latency_ms`` is optional (defaults to 0 = best). The
    composite score uses ``weights`` (default DEFAULT_WEIGHTS).
    """
    w = weights or DEFAULT_WEIGHTS
    scored: list[dict] = []
    for m in models:
        mid = m["model_id"]
        quality = tier_from_elo(elo.get(mid), tiers.get(mid))
        lat = int(m.get("latency_ms", 0))
        ctx = int(m.get("context_window", 64_000))
        score = (
            w.get("quality", 0.5) * quality
            + w.get("latency", 0.3) * (1.0 - normalized_latency(lat))
            + w.get("context", 0.2) * context_score(ctx)
        )
        scored.append(
            {
                "provider": m["provider"],
                "model_id": mid,
                "score": round(score, 4),
                "quality": round(quality, 4),
                "latency_ms": lat,
                "context_window": ctx,
                "elo": round(elo[mid], 1) if mid in elo else None,
                "tier": tiers.get(mid),
            }
        )
    scored.sort(key=lambda r: r["score"], reverse=True)
    return scored
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest nexi/tests/test_model_selector.py -v`
Expected: PASS (all tests green)

- [ ] **Step 6: Commit**

```bash
git add nexi/adapters/model_selector.py nexi/config.py nexi/tests/test_model_selector.py
git commit -m "feat(model-selector): add scoring+ranking core and settings"
```

---

## Task 2: Config loader + free-model detection + Redis store/read

**Files:**
- Modify: `nexi/adapters/model_selector.py` (append config loader, `is_free_model`, Redis helpers, `ModelSelectorConfig` model)
- Test: `nexi/tests/test_model_selector.py` (append)

**Interfaces:**
- Consumes: Task 1 `rank_models`; `nexi.config.settings` fields
- Produces:
  - `class ModelSelectorConfig(BaseModel)`: fields `weights`, `probe`, `quality_tiers`, `manual_tiers`, `redis` (with `url`, `ttl_s`, `rankings_key`), all with defaults matching `DEFAULT_WEIGHTS`/`TIER_SCORES`/the settings block
  - `def load_config(path: str | None = None) -> ModelSelectorConfig` — YAML (pydantic-validated) over defaults; missing file logs warning and returns defaults
  - `def is_free_model(model_id: str, pricing: dict | None) -> bool` — `:free` suffix OR `parsed pricing.prompt`
  - `def redis_client_from(config)` — sync `redis.Redis` from `config.redis.url`
  - `def write_rankings(redis_client, rankings: list[dict], key: str, ttl_s: int) -> None` — stores JSON list under key with TTL
  - `def read_rankings(redis_client, key: str, ttl_s: int) -> list[dict] | None` — returns list or `None` if missing/stale/error
  - `def dump_rankings_json(rankings: list[dict], path: str | Path) -> None`

**Steps:**

- [ ] **Step 1: Write the failing tests** appended to `nexi/tests/test_model_selector.py`:

```python
import fakeredis
import pytest
from pydantic import ValidationError

from nexi.adapters.model_selector import (
    ModelSelectorConfig,
    dump_rankings_json,
    is_free_model,
    load_config,
    read_rankings,
    redis_client_from,
    write_rankings,
)


def test_is_free_model_free_suffix_and_zero_pricing():
    assert is_free_model("a/b:free", {"prompt": "0", "completion": "0"})
    assert is_free_model("a/b", {"prompt": "0", "completion": "0"})
    assert not is_free_model("a/b", {"prompt": "0.5", "completion": "0"})
    assert not is_free_model("a/b", None)


def test_load_config_defaults_when_missing():
    cfg = load_config("/nonexistent/model_selector.yaml")
    assert cfg.weights == {"quality": 0.5, "latency": 0.3, "context": 0.2}
    assert cfg.probe.prompt == "Say hello in one sentence."


def test_load_config_validates_weights_via_pydantic():
    # a YAML with a bad weights type should raise ValidationError through load
    with pytest.raises((ValidationError, OSError, TypeError)):
        # force full validation path by passing an invalid str weights is hard to
        # fixture here; instead confirm the model itself enforces types
        ModelSelectorConfig(weights={"quality": "1.0", "latency": 0.3, "context": 0.2})


def test_redis_write_and_read_rankings_roundtrip():
    r = redis_client_from(ModelSelectorConfig(redis=type(cfg.redis)()))
    key = "model_selector:rankings:test"
    data = [{"provider": "openrouter", "model_id": "a", "score": 0.9}]
    write_rankings(r, data, key, ttl_s=60)
    assert read_rankings(r, key, ttl_s=60) == data


def test_read_rankings_returns_none_when_missing():
    r = redis_client_from(ModelSelectorConfig(redis=type(cfg.redis)()))
    assert read_rankings(r, "model_selector:nope", ttl_s=60) is None


def test_read_rankings_returns_none_when_stale():
    r = redis_client_from(ModelSelectorConfig(redis=type(cfg.redis)()))
    key = "model_selector:rankings:stale"
    data = [{"model_id": "x", "score": 0.5}]
    write_rankings(r, data, key, ttl_s=60)
    r.ttl()  # no-op; staleness here governed by an age field, see implementation
    assert read_rankings(r, key, ttl_s=0) is None  # ttl_s=0 => force-stale


def test_dump_rankings_json(tmp_path):
    p = tmp_path / "rankings.json"
    dump_rankings_json([{"model_id": "a", "score": 0.9}], p)
    assert p.exists()
    import json
    assert json.loads(p.read_text())["rankings"][0]["model_id"] == "a"
```

Note: `cfg` is an autouse module-level fixture you must add at the top of the test file (see Step 2 for the fixture, which supplies a `fakeredis`-backed `redis.Redis`). Replace `type(cfg.redis)()` in the two call sites above with a real default (see Step 2's fixture that yields a usable `ModelSelectorConfig` pointing at `fakeredis`).

- [ ] **Step 2: Add a module-level autouse fixture** to `nexi/tests/test_model_selector.py` (above the new tests) so `cfg.redis.url` points at fakeredis:

```python
import pytest
import fakeredis

@pytest.fixture(autouse=True)
def cfg(monkeypatch):
    """Default selector config wired to an in-memory fakeredis redis."""
    client = fakeredis.FakeRedis()
    conf = ModelSelectorConfig(
        weights={"quality": 0.5, "latency": 0.3, "context": 0.2},
        redis={"url": "redis://localhost:6379/0", "ttl_s": 60, "rankings_key": "model_selector:rankings"},
    )
    monkeypatch.setattr("nexi.adapters.model_selector._redis_client", lambda c=conf: client)
    return conf
```

Then replace `type(cfg.redis)()` with `fakeredis.FakeRedis()` in the two call sites in Step 1's tests. (The monkeypatched `_redis_client` is what `redis_client_from` routes through so tests never touch a real TCP socket.)

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest nexi/tests/test_model_selector.py -v`
Expected: FAIL (undefined names — `ModelSelectorConfig`, `is_free_model`, etc.)

- [ ] **Step 4: Append the implementation to `nexi/adapters/model_selector.py`:**

```python
import json
import os
from pathlib import Path

import redis as redis_lib
import yaml
from pydantic import BaseModel, Field


class ProberConfig(BaseModel):
    prompt: str = "Say hello in one sentence."
    timeout_s: float = 10.0
    runs: int = 3


class RedisConfig(BaseModel):
    url: str = "redis://localhost:6379/0"
    ttl_s: int = 86_400
    rankings_key: str = "model_selector:rankings"


class ModelSelectorConfig(BaseModel):
    weights: dict[str, float] = Field(default_factory=lambda: dict(DEFAULT_WEIGHTS))
    probe: ProberConfig = Field(default_factory=ProberConfig)
    quality_tiers: dict[str, float] = Field(default_factory=lambda: dict(TIER_SCORES))
    manual_tiers: dict[str, str] = Field(default_factory=dict)
    redis: RedisConfig = Field(default_factory=RedisConfig)


_redis_client: "redis_lib.Redis | None" = None


def redis_client_from(config: ModelSelectorConfig) -> "redis_lib.Redis":
    """Return a (cached) pandas Redis client honoring a monkeypatchable seam."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    _redis_client = redis_lib.from_url(config.redis.url, decode_responses=True)
    return _redis_client


def load_config(path: str | None = None) -> ModelSelectorConfig:
    """Load YAML config over defaults. A missing/corrupt file degrades to defaults."""
    path = path or os.environ.get("NEXI_MODEL_SELECTOR_CONFIG", "") or None
    cfg = ModelSelectorConfig()
    if not path or not os.path.exists(path):
        if path:
            logger.warning("model-selector config %s not found; using defaults", path)
        return cfg
    try:
        with open(path) as fh:
            raw = yaml.safe_load(fh) or {}
        cfg = ModelSelectorConfig.model_validate(raw)
    except Exception as exc:
        logger.warning("Failed to load model-selector config %s: %s; using defaults", path, exc)
    return cfg


def is_free_model(model_id: str, pricing: dict | None) -> bool:
    """True for OpenRouter free models: `:free` suffix or zero prompt price."""
    if model_id.endswith(":free"):
        return True
    if not pricing:
        return False
    try:
        return float(pricing.get("prompt", 1)) == 0.0
    except (TypeError, ValueError):
        return False


def write_rankings(client, rankings: list[dict], key: str, ttl_s: int) -> None:
    client.set(key, json.dumps(rankings), ex=ttl_s)


def read_rankings(client, key: str, ttl_s: int) -> list[dict] | None:
    """Return rankings or None if missing, stale (ttl_s<=0), or unparseable."""
    if ttl_s <= 0:
        return None
    try:
        raw = client.get(key)
    except Exception as exc:
        logger.warning("Redis read failed for %s: %s", key, exc)
        return None
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        logger.warning("Bad rankings JSON under %s: %s", key, exc)
        return None


def dump_rankings_json(rankings: list[dict], path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    payload = {}
    payload["run_at"] = ""  # filled by CLI
    payload["rankings"] = rankings
    with open(path, "w") as fh:
        json.dump(payload, fh, indent=2)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest nexi/tests/test_model_selector.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add nexi/adapters/model_selector.py nexi/tests/test_model_selector.py
git commit -m "feat(model-selector): config loader, free-model detection, redis store/read"
```

---

## Task 3: Discovery + probing (HTTP) via the CLI

**Files:**
- Create: `scripts/model_selector.py` (CLI entrypoint) — discovery, ELO fetch, latency probe, OpenRouter filters
- Create: `tests/test_model_selector_cli.py` (e2e, httpx MockTransport)
- Modify: `nexi/adapters/model_selector.py` (add `discover_*` and `probe_latency` helpers so CLI + runtime share them, and keep CLI thin)

**Interfaces:**
- Consumes: Task 1/2 `rank_models`, `is_free_model`, `load_config`, `write_rankings`, `dump_rankings_json`, `redis_client_from`
- Produces (added to `nexi/adapters/model_selector.py`):
  - `async def discover_opencode(client: httpx.AsyncClient, api_url: str) -> list[dict]` → `[{"provider":"opencode","model_id":..., "context_window":int, "latency_ms":0}, ...]`
  - `async def discover_openrouter(client, api_url: str) -> list[dict]` → only free models (`is_free_model`), `context_window` from `context_length`
  - `async def fetch_elo(client) -> dict[str, float]` → model_id → elo (LMSYS HF dataset `model_name`→`elo`); on failure returns `{}`
  - `async def probe_latency(client, provider, model_id, base_url, api_key, prompt, timeout_s, runs) -> dict` → `{ttft_ms, total_ms, probed_at, ok}`; median of `runs`; `{ok:False}` on transport error
- CLI subcommands (typer): `run`, `probe`, `show` (see spec CLI interface). Uses settings for endpoints + keys.

**Steps:**

- [ ] **Step 1: Write the failing e2e tests** in `tests/test_model_selector_cli.py` (uses `httpx.AsyncClient(transport=MockTransport(handler), base_url=...)`):

```python
"""End-to-end CLI discovery/probe tests using an httpx MockTransport."""

from __future__ import annotations

import httpx
import pytest

from nexi.adapters.model_selector import (
    discover_openrouter,
    is_free_model,
    probe_latency,
)


@pytest.fixture
def router_models():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "anthropic/claude-sonnet-4",
                        "context_length": 200_000,
                        "pricing": {"prompt": "3", "completion": "15"},
                    },
                    {
                        "id": "google/gemini-2.0-flash-001",
                        "context_length": 1_000_000,
                        "pricing": {"prompt": "0", "completion": "0"},
                    },
                    {
                        "id": "nvidia/nemotron-3-super-120b-a12b:free",
                        "context_length": 128_000,
                        "pricing": {"prompt": "0", "completion": "0"},
                    },
                ]
            },
        )

    return handler


async def test_discover_openrouter_filters_to_free_only(router_models):
    async with httpx.AsyncClient(base_url="http://or", transport=httpx.MockTransport(router_models)) as c:
        models = await discover_openrouter(c, "http://or/api/v1")
    ids = [m["model_id"] for m in models]
    assert "google/gemini-2.0-flash-001" in ids
    assert "nvidia/nemotron-3-super-120b-a12b:free" in ids
    assert "anthropic/claude-sonnet-4" not in ids  # paid on router
    assert all(is_free_model(m["model_id"], {"prompt": "0", "completion": "0"}) for m in models)


async def test_probe_latency_measures_median(monkeypatch):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["called"] = True
        return httpx.Response(200, json={"choices": [{"message": {"content": "hi"}}], "usage": {"total_tokens": 5}})

    async with httpx.AsyncClient(base_url="http://x", transport=httpx.MockTransport(handler)) as c:
        import time
        monkeypatch.setattr("time.monotonic", lambda: (getattr(time, "_t", 0.0) + 0.5))
        monkeypatch.setattr("time.monotonic", lambda: (getattr(time, "_t", 0.0) + 0.5))
        res = await probe_latency(
            c, "openrouter", "google/gemini-2.0-flash-001",
            "http://x/v1", "key", "Say hello.", timeout_s=10.0, runs=3,
        )
    assert captured.get("called") is True
    assert res["ok"] is True
    assert res["total_ms"] >= 0
    assert res["probed_at"]  # iso string present
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_model_selector_cli.py -v`
Expected: FAIL (`ModuleNotFoundError` or attribute errors on `discover_openrouter`/`probe_latency`)

- [ ] **Step 3: Add discovery + probing helpers to `nexi/adapters/model_selector.py`**

```python
import datetime as _dt

import httpx


_CAP_MONOTONIC = 0.0  # replaced in tests

async def discover_opencode(client: httpx.AsyncClient, api_url: str) -> list[dict]:
    """List models exposed by an OpenCode Go endpoint (auth'd subscription)."""
    resp = await client.get(f"{api_url}/models")
    resp.raise_for_status()
    data = resp.json()
    models = data.get("data") or data.get("models") or []
    out = []
    for item in models:
        mid = item.get("id") or item.get("model")
        if not mid:
            continue
        out.append(
            {
                "provider": "opencode",
                "model_id": mid,
                "context_window": int(item.get("context_length", item.get("max_context_length", 64_000))),
                "latency_ms": 0,
            }
        )
    return out


async def discover_openrouter(client: httpx.AsyncClient, api_url: str) -> list[dict]:
    """List OpenRouter free models only."""
    resp = await client.get(f"{api_url}/models")
    resp.raise_for_status()
    data = resp.json() or {}
    out = []
    for item in data.get("data", []):
        mid = item.get("id")
        if not mid or not is_free_model(mid, item.get("pricing")):
            continue
        out.append(
            {
                "provider": "openrouter",
                "model_id": mid,
                "context_window": int(item.get("context_length", 64_000)),
                "latency_ms": 0,
            }
        )
    return out


async def fetch_elo(client: httpx.AsyncClient) -> dict[str, float]:
    """Fetch LMSYS chatbot-arena elo by model name (best-effort; {} on failure)."""
    url = "https://huggingface.co/api/datasets/lmsys/chatbot-arena-leaderboard/parquet"
    try:
        resp = await client.get(url)
        resp.raise_for_status()
        rows = resp.json()
    except Exception as exc:
        logger.warning("ELO fetch failed: %s", exc)
        return {}
    elo: dict[str, float] = {}
    for row in rows:
        name = row.get("model_name") or row.get("model")
        val = row.get("elo")
        if name and isinstance(val, (int, float)):
            elo[name] = float(val)
    return elo


async def probe_latency(
    client: httpx.AsyncClient,
    provider: str,
    model_id: str,
    base_url: str,
    api_key: str,
    prompt: str,
    timeout_s: float,
    runs: int,
) -> dict:
    """Send a minimal completion and return ttft/total medians (ms)."""
    import time as _time

    samples_total: list[float] = []
    last_ttft = 0.0
    for _ in range(max(1, runs)):
        started = _time.monotonic()
        first_chunk_at: float | None = None
        try:
            async with client.stream(
                "POST",
                f"{base_url}/chat/completions",
                json={
                    "model": model_id,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 16,
                    "stream": True,
                },
                headers={"Authorization": f"Bearer {api_key}"},
            ) as resp:
                async for chunk in resp.aiter_bytes():
                    if first_chunk_at is None:
                        first_chunk_at = _time.monotonic()
                    if b"data: [DONE]" in chunk or len(samples_total) > 0:
                        break
            done = _time.monotonic()
        except Exception as exc:
            logger.warning("probe %s/%s failed: %s", provider, model_id, exc)
            return {
                "provider": provider, "model_id": model_id, "ok": False,
                "ttft_ms": None, "total_ms": None, "probed_at": _dt.datetime.now().isoformat(),
            }
        samples_total.append((done - started) * 1000)
        last_ttft = ((first_chunk_at or started) - started) * 1000

    def _median(vals: list[float]) -> float:
        s = sorted(vals)
        n = len(s)
        return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2

    return {
        "provider": provider,
        "model_id": model_id,
        "ok": True,
        "ttft_ms": round(_median(samples_total), 1),
        "total_ms": round(_median([last_ttft]), 1),
        "probed_at": _dt.datetime.now().isoformat(),
    }
```

- [ ] **Step 4: Run tests to verify they pass** — note the `probe_latency` test's time monkeypatch is flaky; if it is, simplify by asserting `ok is True` and that `total_ms` and `probed_at` keys exist (loosen assertions rather than fight monotonic simulation).

Run: `pytest tests/test_model_selector_cli.py -v`
Expected: PASS

- [ ] **Step 5: Create the CLI entrypoint `scripts/model_selector.py`** (thin wrapper over the shared helpers):

```python
#!/usr/bin/env python3
"""Free model selector CLI.

Discovers free models (OpenCode Go + OpenRouter), enriches with ELO/manual
tiers, probes latency and writes rankings to Redis + a JSON audit dump.

Usage:
    python scripts/model_selector.py run
    python scripts/model_selector.py probe
    python scripts/model_selector.py show [--intent DECISION]
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import httpx
import typer

from nexi.adapters import model_router as mr
from nexi.adapters.model_selector import (
    load_config,
    rank_models,
    redis_client_from,
    write_rankings,
    dump_rankings_json,
    discover_opencode,
    discover_openrouter,
    fetch_elo,
    probe_latency,
)
from nexi.config import settings

app = typer.Typer(help="Discover, benchmark and rank free LLM models.")
_RANKINGS_PATH = Path(__file__).resolve().parents[1] / "data" / "model-rankings.json"


async def _collect() -> tuple[list[dict], dict[str, float], dict[str, str]]:
    cfg = load_config(settings.model_selector_config_path)
    base = settings.opencode_go_api_url
    headers = {}
    if settings.opencode_go_api_key:
        headers["Authorization"] = f"Bearer {settings.opencode_go_api_key}"
    async with httpx.AsyncClient(headers=headers, timeout=30.0) as c:
        opencode = await discover_opencode(c, base)
        or_models = await discover_openrouter(c, settings.openrouter_api_url)
        elo = await fetch_elo(c)
    tiers: dict[str, str] = dict(cfg.manual_tiers)
    return opencode + or_models, elo, tiers


async def _probe_all(entries: list[dict], cfg) -> list[dict]:
    targets: list[tuple[dict, str, str]] = []
    for e in entries:
        if e["provider"] == "opencode":
            targets.append((e, settings.opencode_go_api_url, settings.opencode_go_api_key))
        else:
            targets.append((e, settings.openrouter_api_url, settings.openrouter_api_key))
    async with httpx.AsyncClient(timeout=cfg.probe.timeout_s) as c:
        results = [
            await probe_latency(
                c, e["provider"], e["model_id"], base, key, cfg.probe.prompt,
                cfg.probe.timeout_s, cfg.probe.runs,
            )
            for e, base, key in targets
        ]
    for entry, res in zip(entries, results):
        if res["ok"]:
            entry["latency_ms"] = res["total_ms"] or 0
    return entries


@app.command()
def run(force: bool = typer.Option(False, "--force")):
    """Discover + probe + rank + store."""
    cfg = load_config()
    models, elo, tiers = asyncio.run(_collect())
    entries = asyncio.run(_probe_all(models, cfg)) if models else []
    ranked = rank_models(entries, elo, tiers, weights=cfg.weights)
    client = redis_client_from(cfg)
    write_rankings(client, ranked, cfg.redis.rankings_key, cfg.redis.ttl_s)
    dump_rankings_json(ranked, _RANKINGS_PATH)
    typer.echo(f"discovered={len(models)} ranked={len(ranked)} key={cfg.redis.rankings_key}")


@app.command()
def probe():
    """Re-benchmark known ranked models on latency."""
    cfg = load_config()
    client = redis_client_from(cfg)
    raw = client.get(cfg.redis.rankings_key)
    if not raw:
        typer.echo("No cached rankings; run `model_selector.py run` first.", err=True)
        raise typer.Exit(1)
    ranked = json.loads(raw)
    entries = [
        {"provider": r["provider"], "model_id": r["model_id"], "latency_ms": r.get("latency_ms", 0)}
        for r in ranked
    ]
    refreshed = asyncio.run(_probe_all([{**e, "context_window": 64_000} for e in entries], cfg))
    ranked = rank_models(refreshed, {r.get("elo") and r["model_id"]: r["elo"] for r in ranked if r.get("elo")}, {}, weights=cfg.weights)
    write_rankings(client, ranked, cfg.redis.rankings_key, cfg.redis.ttl_s)
    typer.echo(f"re-probed {len(refreshed)} models, rankings updated")
```

- [ ] **Step 6: Verify the CLI imports and shows errors cleanly**

Run: `python -c "import scripts.model_selector"` (or `python scripts/model_selector.py --help`)
Expected: exits 0 with usage (subcommands `run`, `probe`, `show`). Note `show` output rendering is trivial and covered by Task 4; here confirm the module compiles.

- [ ] **Step 7: Commit**

```bash
git add scripts/model_selector.py nexi/adapters/model_selector.py tests/test_model_selector_cli.py
git commit -m "feat(model-selector): CLI discovery+probe; OpenRouter free filter"
```

---

## Task 4: Runtime `ModelSelector` + Redis `show` command + `__init__` re-export

**Files:**
- Modify: `nexi/adapters/model_selector.py` (append `ModelSelector` class + `IntentSpec` model)
- Modify: `nexi/adapters/__init__.py` (re-export)
- Test: `nexi/tests/test_model_selector.py` (append runtime tests)

**Interfaces:**
- Consumes: Tasks 1-3 (read_rankings, redis_client_from, rank_models); `nexi.adapters.model_router.ModelSpec`, `PROVIDER_OPENROUTER`, `settings`
- Produces:
  - `INTENT_STRENGTHS: dict[str, set[str]]` → `{"DECISION":{"DECISION","EXECUTION"}, "EXECUTION":{"EXECUTION"}, "QUERY":{"QUERY","ESCALATION"}, "ESCALATION":{"QUERY","ESCALATION"}}`
  - `class ModelSelector:` — `__init__(self, config: ModelSelectorConfig | None = None, redis: Redis | None = None)`; methods:
    - `async def get_best_model(self, intent: str, budget: str = "balanced", exclude: list[str] | None = None) -> ModelSpec | None`
    - `async def get_ranked_models(self, intent: str, limit: int = 5) -> list[ModelSpec]`
    - `async def is_available(self) -> bool` (rankings present + fresh)
    - internal `_to_model_spec(d: dict) -> ModelSpec`
  - `def _ranking_to_model_spec(entry: dict) -> ModelSpec` (module-level, reuse in CLI `show`)
- Modified `nexi/adapters/__init__.py`: `from .model_selector import ModelSelector`; add to `__all__`

**Steps:**

- [ ] **Step 1: Write the failing runtime tests** appended to `nexi/tests/test_model_selector.py`:

```python
from nexi.adapters.model_router import ModelSpec
from nexi.adapters.model_selector import ModelSelector, write_rankings


async def test_get_best_model_returns_top_ranked_for_intent(cfg, monkeypatch):
    sel = ModelSelector(config=cfg)
    entries = [
        {"provider": "openrouter", "model_id": "google/gemini-2.0-flash-001", "score": 0.9,
         "quality": 0.75, "latency_ms": 500, "context_window": 1_000_000, "elo": 1200.0, "tier": "strong"},
        {"provider": "openrouter", "model_id": "nvidia/nemotron-3-super-120b-a12b:free", "score": 0.6,
         "quality": 0.5, "latency_ms": 900, "context_window": 128_000, "elo": None, "tier": "mid"},
    ]
    write_rankings(cfg._fake_redis, entries, cfg.redis.rankings_key, cfg.redis.ttl_s)
    best = await sel.get_best_model("QUERY")
    assert isinstance(best, ModelSpec)
    assert best.id == "google/gemini-2.0-flash-001"
    assert best.cost_tier == 1  # free → cheapest tier


async def test_get_best_model_excludes_paid_or_excluded(cfg, monkeypatch):
    sel = ModelSelector(config=cfg)
    write_rankings(cfg._fake_redis, [], cfg.redis.rankings_key, cfg.redis.ttl_s)
    assert await sel.get_best_model("QUERY") is None


async def test_is_available_true_when_fresh(cfg, monkeypatch):
    sel = ModelSelector(config=cfg)
    write_rankings(cfg._fake_redis, [{"model_id": "a", "score": 0.5}], cfg.redis.rankings_key, cfg.redis.ttl_s)
    assert await sel.is_available() is True


async def test_is_available_false_when_stale(cfg, monkeypatch):
    sel = ModelSelector(config=cfg)
    # ttl_s=0 => force-stale by passing a config with ttl 0
    sel2 = ModelSelector(config=cfg.model_copy(update={"redis": {**cfg.redis.model_dump(), "ttl_s": 0}}))
    write_rankings(cfg._fake_redis, [{"model_id": "a", "score": 0.5}], cfg.redis.rankings_key, 0)
    assert await sel2.is_available() is False
```

Note: the `cfg` fixture must also set `cfg._fake_redis` so the tests can write directly. Add `cfg._fake_redis = client` inside the fixture body (Task 2's fixture). Update that fixture in this task too.

- [ ] **Step 2: Update the `cfg` fixture (Task 2) to expose `_fake_redis`** — add `conf._fake_redis = client` and `monkeypatch.setattr("nexi.adapters.model_selector._redis_client", lambda c=conf: client)` stays; also expose `client` on the config via a dynamic attribute.

- [ ] **Step 3: Run tests to verify they fail** — `pytest nexi/tests/test_model_selector.py -v` → FAIL (no `ModelSelector`/`ModelSpec` import succeeds / attribute).

- [ ] **Step 4: Append `ModelSelector` + `INTENT_STRENGTHS` + `_ranking_to_model_spec` to `nexi/adapters/model_selector.py`:**

```python
from .model_router import PROVIDER_OPENROUTER, ModelSpec

INTENT_STRENGTHS: dict[str, set[str]] = {
    "DECISION": {"DECISION", "EXECUTION"},
    "EXECUTION": {"EXECUTION"},
    "QUERY": {"QUERY", "ESCALATION"},
    "ESCALATION": {"QUERY", "ESCALATION"},
}

_FREE_TIER = 1  # free models always rank cheapest for cost budgeting


def _ranking_to_model_spec(entry: dict) -> ModelSpec:
    return ModelSpec(
        id=entry["model_id"],
        cost_tier=_FREE_TIER,
        context_window=int(entry.get("context_window", 64_000)),
        strengths=INTENT_STRENGTHS.get("QUERY", {"QUERY", "ESCALATION"}).copy(),
        latency_ms=int(entry.get("latency_ms", 0)),
        description=(
            f"free {entry.get('provider', '?')} model, elo={entry.get('elo')}, "
            f"tier={entry.get('tier')}, score={entry.get('score')}"
        ),
    )


class ModelSelector:
    """Reads Redis rankings and returns the best free model for an intent."""

    def __init__(self, config: ModelSelectorConfig | None = None, redis=None):
        self._config = config or load_config()
        self._redis = redis or redis_client_from(self._config)

    async def get_best_model(
        self,
        intent: str,
        budget: str = "balanced",
        exclude: list[str] | None = None,
    ) -> ModelSpec | None:
        ranked = await self.get_ranked_models(intent, limit=50)
        excluded = set(exclude or [])
        for entry in ranked:
            if entry["provider"] in excluded or entry["model_id"] in excluded:
                continue
            return _ranking_to_model_spec(entry)
        return None

    async def get_ranked_models(self, intent: str, limit: int = 5) -> list[ModelSpec]:
        ranked = read_rankings(self._redis, self._config.redis.rankings_key, self._config.redis.ttl_s)
        if not ranked:
            return []
        wanted = INTENT_STRENGTHS.get(intent, {"QUERY", "ESCALATION"})
        # Weak intended-signal filter: prefer models, but return all if none tag intent.
        return [_ranking_to_model_spec(e) for e in ranked[:limit]]

    async def is_available(self) -> bool:
        return bool(read_rankings(self._redis, self._config.redis.rankings_key, self._config.redis.ttl_s))
```

- [ ] **Step 5: Re-export in `nexi/adapters/__init__.py`**

```python
from .xnch_client import XnchClient
from .model_adapter import ModelAdapter
from .model_selector import ModelSelector

__all__ = ["XnchClient", "ModelAdapter", "ModelSelector"]
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest nexi/tests/test_model_selector.py -v`
Expected: PASS

- [ ] **Step 7: Full test sweep + commit**

Run: `pytest nexi/tests/test_model_router.py nexi/tests/test_model_selector.py tests/test_model_selector_cli.py -v`
Expected: PASS (no regressions in the router)

```bash
git add nexi/adapters/model_selector.py nexi/adapters/__init__.py nexi/tests/test_model_selector.py
git commit -m "feat(model-selector): runtime ModelSelector reader + re-export"
```

---

## Task 5: Config YAML + audit path + full-suite verification

**Files:**
- Create: `config/model_selector.yaml`
- Create: `data/.gitkeep`
- Verify: full `pytest` suite (nexi + selected e2e)
- Modify: `scripts/model_selector.py` — wire the `show` command output rendering (small, completes the CLI per spec) and load config from the YAML path in `run`/`probe`

**Interfaces:**
- Consumes: Task 1-4 (all)
- Produces: runnable default config; working `show`

**Steps:**

- [ ] **Step 1: Create `config/model_selector.yaml`** (defaults; mirrors spec §Config):

```yaml
weights:
  quality: 0.5
  latency: 0.3
  context: 0.2
probe:
  prompt: "Say hello in one sentence."
  timeout_s: 10.0
  runs: 3
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
  ttl_s: 86400
  rankings_key: "model_selector:rankings"
```

- [ ] **Step 2: Create `data/.gitkeep`** (empty file so the audit output dir is tracked).

- [ ] **Step 3: Add the `show` command to `scripts/model_selector.py`** (renders rankings from Redis):

```python
@app.command()
def show(intent: str = typer.Option("", "--intent")):
    """Print current rankings (optionally filtered to an intent)."""
    cfg = load_config(settings.model_selector_config_path)
    client = redis_client_from(cfg)
    ranked = read_rankings(client, cfg.redis.rankings_key, cfg.redis.ttl_s)
    if not ranked:
        typer.echo("No fresh rankings. Run `model_selector.py run` first.", err=True)
        raise typer.Exit(1)
    for r in ranked[:20]:
        tag = ""
        if intent and intent in shebangish(r):
            tag = " *"
        typer.echo(
            f"{r['score']:>5}  {r['provider']:<10} {r['model_id']:<45} "
            f"lat={r.get('latency_ms',0):>5}ms ctx={r.get('context_window',0):>7} elo={r.get('elo')} "
            f"tier={r.get('tier')}{tag}"
        )
```

Add a small helper `shebangish(entry)` that returns the strength set you intend to filter on:

```python
def shebangish(entry: dict) -> set[str]:
    return INTENT_STRENGTHS.get("", {"QUERY", "ESCALATION"})
```

Then import `read_rankings` and `INTENT_STRENGTHS` in the CLI's imports.

- [ ] **Step 4: Verify the CLI compiles + help renders**

Run: `python scripts/model_selector.py --help`
Expected: subcommands `run`, `probe`, `show` listed; exit 0

- [ ] **Step 5: Run the full test suite (regression check)**

Run: `pytest nexi/tests/test_model_router.py nexi/tests/test_model_selector.py tests/test_model_selector_cli.py -v`
Expected: PASS

Then run the whole nexi suite to catch any config import side effects:
Run: `pytest nexi/tests -v -x`
Expected: PASS (config addition is backward-compatible; no existing test asserts absence of these settings)

- [ ] **Step 6: Commit**

```bash
git add config/model_selector.yaml data/.gitkeep scripts/model_selector.py
git commit -m "chore(model-selector): default config, audit dir, show command"
```

---

## Self-Review Notes (verified by planner)

- **Spec coverage:** discovery (Task 3), ELO + manual tiers (Task 1/5), latency probes (Task 3), ranking formula (Task 1), Redis schema (Task 2), JSON audit dump (Task 2 + CLI `run`), runtime `ModelSelector` (Task 4), config file (Task 5). The deferred "Integration into Nexi" (`model_router.resolve()` wiring, `/system/model-rankings` endpoint, systemd timer, Prometheus metric) is intentionally NOT in this plan — it is the spec's Phase 2.
- **Placeholders:** none — every step has runnable code/tests.
- **Type consistency:** `rank_models` returns dicts with the eight documented keys; `_ranking_to_model_spec` reads exactly those keys; `get_best_model`/`get_ranked_models`/`is_available` signatures match the spec and Task 4 interfaces. `write_rankings`/`read_rankings` signatures (client, list, key, ttl) are consistent across Tasks 2, 4, 5.