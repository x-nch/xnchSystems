# Phase 2 — Memory-Service Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract xnch's L0–L3 memory stores (pgvector episodic, Redis sensory/working, Kuzu graph, relationships, scraper documents, consolidation) into an independently deployable **memory-service** on node-a :8003, with the gateway behind a `MemoryClient`, an `XNCH_MEMORY_EMBEDDED=1` rollback switch, and a degrade/replay path.

**Architecture:** Spec option (b) — new entrypoint `python -m xnch.memory.server` INSIDE the xnch submodule (no code moves across repo boundaries, all existing store tests stay valid). The service exposes one whitelisted generic dispatch endpoint (`POST /v1/call`), plus `/healthz`, `/v1/consolidation/run`, and `/v1/graph/stream` (SSE). The gateway's lifespan delegates to `xnch/memory/bootstrap.py::build_memory()`, which constructs either the real stores (embedded, default — bit-identical to today) or thin remote refs (`RemoteStoreRef` async for async stores; `RemoteGraphStore` sync+blocking for the Kuzu store so the ~15 sync call sites in routes/jobs/pipeline need zero changes). Kuzu is in-process/single-file, so exactly one process may own it — this is what makes the extraction mandatory rather than optional.

**Tech Stack:** FastAPI, uvicorn, httpx, redis.asyncio, asyncpg, Kuzu, pytest (asyncio_mode=auto).

**Spec:** `docs/superpowers/specs/2026-09-11-micro-component-split.md` §5.7 — implements T2.1 (server), T2.2 (MemoryClient + embedded switch), T2.3 (lifespan swap), T2.4 (degrade path), T2.5 (deploy), T2.6 (runbook).

## Global Constraints

- External contracts frozen: `xnch_*`/`am_*` MCP tools, web UI, chat API, agent-runner dispatch, gateway route schemas — unchanged.
- `xnch/` is a git submodule: all `xnch/...` changes are committed inside the submodule first; the superrepo gitlink is bumped at the end (Task 10).
- `XNCH_MEMORY_EMBEDDED` defaults to **true** — deploying this plan's code changes nothing until ops flips it. Rollback = flip back + restart.
- Fail-closed token auth on the service (`XNCH_MEMORY_TOKEN`; unset token = 503, never open).
- The LangGraph opt-in pipeline (`XNCH_LANGGRAPH_PIPELINE=1`) receives raw store objects and makes sync graph calls — it is **incompatible with remote mode**. The lifespan must guard it (warning + skip) rather than crash. Documented in the runbook.
- All new code follows AGENTS.md conventions: modern unions, `Annotated`, snake_case, Pydantic models, `logging.getLogger(__name__)`, relative imports inside xnch.
- Ports: memory-service `:8003` on **node-a** (node-b's old fs sidecar on :8003 is a different host and was merged away in Phase 1 anyway; perception uses :8002 on node-a).
- Run `pytest` from repo root with repo `.venv` active. Tests must not require a live Postgres/Kuzu/Redis — use fakes and `httpx.MockTransport`.

## Grounded consumer surface (what the client must proxy — verified by grep, keep in sync)

| Store | Methods called from gateway-side code (routes/jobs/learning/agents/xnch_mcp) |
|---|---|
| pg_episodic | store_episode, store_decision_episode, complete_decision_episode, write_prediction_update, retrieve_similar, has_identical_recent, list_recent, bump_recall, fetch_by_type, fetch_for_manifest, fetch_patterns_for_manifest, fetch_episodes_for_decay, fetch_decision_episodes_since, fetch_decision_episodes_with_scores, fetch_unextracted_for_graph, mark_graph_extracted, has_episode_of_type, upsert_pattern, fetch_all_patterns, fetch_patterns_low_success, apply_decay, apply_decay_batch, store_session_episode, ledger_mark_done, ledger_mark_failed, ledger_completed_ids, ledger_get |
| graph_store (SYNC) | upsert_entity, upsert_relation (async), get_entity_by_name, get_entity, fetch_entities, query_entity_connections, get_stats, get_subgraph, list_entities, list_relations, count_entities, count_relations |
| relationship_store | upsert_relationship, get_relationships, get_relationship_strength |
| working_memory | set_context, get_context, get_full_session, clear_session, append_turn, get_turns |
| sensory_buffer | write_perception, read_recent, flush_to_working_memory |
| scraped_store | store, query, delete_by_url, count |

The whitelist in Task 3 is exactly this table. Adding a method later = add one tuple to `_ALLOWED` + one test.

## File Structure

```
xnch/memory/
  server.py          # NEW — FastAPI app factory + /v1/call dispatch + /healthz + SSE + __main__
  client.py          # NEW — RemoteStoreRef (async), RemoteGraphStore (sync), DegradingEpisodic, replay loop
  bootstrap.py       # NEW — build_memory(settings) -> MemoryBackends (embedded|remote), MemoryBackends.aclose()
  tests/
    test_memory_server.py      # NEW — dispatch whitelist, token, healthz, SSE
    test_memory_client.py     # NEW — refs, degrade, replay
    test_memory_bootstrap.py  # NEW — mode selection, langgraph guard logic
xnch/config.py       # MODIFY — memory_embedded, memory_service_url, memory_service_token
xnch/main.py         # MODIFY — lifespan uses build_memory(); shutdown via s.memory.aclose(); graph_stream relay flag
xnch/routes/memory.py # MODIFY — /graph/stream relay branch when broadcaster is None
infra/no-k3s/node-a/systemd/xnch-memory.service   # NEW
infra/no-k3s/node-a/systemd/consolidation.service  # MODIFY — curl retarget with token
docs/runbooks/memory-service-deploy.md             # NEW — cutover + rollback
docs/reference/env-vars.md                         # MODIFY
```

---

### Task 1: Baseline + preconditions

- [ ] **Step 1: Run full suite**

Run: `pytest --tb=short -q`
Expected: green (or same failures as recorded in Phase 1 Task 1's `misc/phase1-baseline.txt`).

- [ ] **Step 2: OPS CHECK (node-a, user-run)**

`ss -ltn | grep 8003` on node-a → empty (else pick another port and update this plan + spec before proceeding). Also confirm `XNCH_LANGGRAPH_PIPELINE` is unset/`0` in `~/.xnch/xnch.env` (remote mode skips the LangGraph runtime with a warning — see Task 9).

---

### Task 2: Settings (xnch submodule)

**Files:**
- Modify: `xnch/config.py` (after `memory_routing_policy_path`, ~line 182)
- Test: `xnch/tests/test_memory_settings.py` (new)

**Interfaces:**
- Produces: `Settings.memory_embedded: bool = True` (`XNCH_MEMORY_EMBEDDED`), `Settings.memory_service_url: str = "http://127.0.0.1:8003"` (`XNCH_MEMORY_SERVICE_URL`), `Settings.memory_service_token: str = ""` (`XNCH_MEMORY_TOKEN`).

- [ ] **Step 1: Write the failing test**

```python
"""Memory-service settings: embedded default + remote flip."""

from __future__ import annotations

from xnch.config import Settings


def test_memory_settings_default_embedded() -> None:
    s = Settings(_env_file=None)
    assert s.memory_embedded is True
    assert s.memory_service_url == "http://127.0.0.1:8003"
    assert s.memory_service_token == ""


def test_memory_settings_remote_mode(monkeypatch) -> None:
    monkeypatch.setenv("XNCH_MEMORY_EMBEDDED", "false")
    monkeypatch.setenv("XNCH_MEMORY_SERVICE_URL", "http://192.168.50.1:8003")
    monkeypatch.setenv("XNCH_MEMORY_TOKEN", "sekrit")
    s = Settings(_env_file=None)
    assert s.memory_embedded is False
    assert s.memory_service_url == "http://192.168.50.1:8003"
    assert s.memory_service_token == "sekrit"
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest xnch/tests/test_memory_settings.py -v`
Expected: FAIL — `AttributeError: ... no attribute 'memory_embedded'`

- [ ] **Step 3: Add to `xnch/config.py`** (after `memory_routing_policy_path`)

```python
    # Memory service (Phase 2 extraction; embedded default keeps behavior)
    memory_embedded: bool = True
    memory_service_url: str = "http://127.0.0.1:8003"
    memory_service_token: str = ""
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest xnch/tests/test_memory_settings.py -v` → 2 PASS

- [ ] **Step 5: Commit (inside xnch submodule)**

```bash
git -C xnch add xnch/config.py xnch/tests/test_memory_settings.py
git -C xnch commit -m "feat: memory-service settings (embedded default, url, token)"
```

---

### Task 3: Server — app factory, token, `/v1/call` whitelist dispatch

**Files:**
- Create: `xnch/memory/server.py`
- Test: `xnch/tests/test_memory_server.py` (new)

**Interfaces:**
- Consumes: `Settings.memory_service_token` (Task 2).
- Produces: `build_app(store_factory: Callable[[], MemoryServiceStores] | None = None) -> FastAPI` with `POST /v1/call` body `{"store": str, "method": str, "args": list, "kwargs": dict}` → `{"result": Any}`; `MemoryServiceStores` dataclass (fields exactly: `pg_episodic, graph_store, relationship_store, working_memory, sensory_buffer, scraped_store, broadcaster`).

- [ ] **Step 1: Write the failing tests**

```python
"""Memory service: /v1/call whitelist dispatch + fail-closed token."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from xnch.memory.server import MemoryServiceStores, build_app


class _FakePg:
    async def retrieve_similar(self, query_text: str | None = None, top_k: int = 5) -> list[dict[str, Any]]:
        return [{"id": "e1", "raw_text": "hello", "similarity": 0.9}]

    async def store_episode(self, type_: str, raw_text: str | None = None) -> str:
        return f"mem-{type_}"


class _FakeGraph:
    def get_stats(self) -> dict[str, Any]:
        return {"entity_count": 3, "relation_count": 5}


def _stores() -> MemoryServiceStores:
    return MemoryServiceStores(
        pg_episodic=_FakePg(),
        graph_store=_FakeGraph(),
        relationship_store=None,
        working_memory=None,
        sensory_buffer=None,
        scraped_store=None,
        broadcaster=None,
    )


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch):
    from xnch.config import settings as xnch_settings

    monkeypatch.setattr(xnch_settings, "memory_service_token", "sekrit")
    return build_app(store_factory=_stores)


def _client(app) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_call_unauthorized_401(app) -> None:
    async with _client(app) as client:
        resp = await client.post(
            "/v1/call", json={"store": "pg_episodic", "method": "retrieve_similar"}
        )
    assert resp.status_code == 401


async def test_call_token_not_configured_503(monkeypatch: pytest.MonkeyPatch) -> None:
    from xnch.config import settings as xnch_settings

    monkeypatch.setattr(xnch_settings, "memory_service_token", "")
    app = build_app(store_factory=_stores)
    async with _client(app) as client:
        resp = await client.post(
            "/v1/call",
            json={"store": "pg_episodic", "method": "retrieve_similar"},
            headers={"X-Internal-Token": "x"},
        )
    assert resp.status_code == 503


async def test_call_async_method(app) -> None:
    async with _client(app) as client:
        resp = await client.post(
            "/v1/call",
            json={"store": "pg_episodic", "method": "retrieve_similar",
                  "kwargs": {"query_text": "hi", "top_k": 3}},
            headers={"X-Internal-Token": "sekrit"},
        )
    assert resp.status_code == 200
    assert resp.json()["result"][0]["raw_text"] == "hello"


async def test_call_sync_method(app) -> None:
    async with _client(app) as client:
        resp = await client.post(
            "/v1/call",
            json={"store": "graph_store", "method": "get_stats"},
            headers={"X-Internal-Token": "sekrit"},
        )
    assert resp.status_code == 200
    assert resp.json()["result"]["entity_count"] == 3


async def test_call_not_whitelisted_403(app) -> None:
    async with _client(app) as client:
        resp = await client.post(
            "/v1/call",
            json={"store": "pg_episodic", "method": "execute"},
            headers={"X-Internal-Token": "sekrit"},
        )
    assert resp.status_code == 403


async def test_call_unknown_store_404(app) -> None:
    async with _client(app) as client:
        resp = await client.post(
            "/v1/call",
            json={"store": "kv_cache", "method": "ping"},
            headers={"X-Internal-Token": "sekrit"},
        )
    assert resp.status_code == 404
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest xnch/tests/test_memory_server.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'xnch.memory.server'`

- [ ] **Step 3: Implement `xnch/memory/server.py` (part 1)**

```python
"""Memory service — L0-L3 stores over internal HTTP (node-a).

Run:  XNCH_MEMORY_BIND=0.0.0.0 XNCH_MEMORY_PORT=8003 python -m xnch.memory.server
"""

from __future__ import annotations

import asyncio
import inspect
import secrets
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Annotated, Any, Callable

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

_ALLOWED: frozenset[tuple[str, str]] = frozenset(
    {
        *(
            ("pg_episodic", m)
            for m in (
                "store_episode", "store_decision_episode", "complete_decision_episode",
                "write_prediction_update", "retrieve_similar", "has_identical_recent",
                "list_recent", "bump_recall", "fetch_by_type", "fetch_for_manifest",
                "fetch_patterns_for_manifest", "fetch_episodes_for_decay",
                "fetch_decision_episodes_since", "fetch_decision_episodes_with_scores",
                "fetch_unextracted_for_graph", "mark_graph_extracted",
                "has_episode_of_type", "upsert_pattern", "fetch_all_patterns",
                "fetch_patterns_low_success", "apply_decay", "apply_decay_batch",
                "store_session_episode", "ledger_mark_done", "ledger_mark_failed",
                "ledger_completed_ids", "ledger_get",
            )
        ),
        *(
            ("graph_store", m)
            for m in (
                "upsert_entity", "upsert_relation", "get_entity_by_name", "get_entity",
                "fetch_entities", "query_entity_connections", "get_stats", "get_subgraph",
                "list_entities", "list_relations", "count_entities", "count_relations",
            )
        ),
        *(
            ("relationship_store", m)
            for m in ("upsert_relationship", "get_relationships", "get_relationship_strength")
        ),
        *(
            ("working_memory", m)
            for m in (
                "set_context", "get_context", "get_full_session", "clear_session",
                "append_turn", "get_turns",
            )
        ),
        *(
            ("sensory_buffer", m)
            for m in ("write_perception", "read_recent", "flush_to_working_memory")
        ),
        *(
            ("scraped_store", m)
            for m in ("store", "query", "delete_by_url", "count")
        ),
    }
)


@dataclass
class MemoryServiceStores:
    pg_episodic: Any
    graph_store: Any
    relationship_store: Any
    working_memory: Any
    sensory_buffer: Any
    scraped_store: Any
    broadcaster: Any = None


class CallRequest(BaseModel):
    store: str
    method: str
    args: list[Any] = Field(default_factory=list)
    kwargs: dict[str, Any] = Field(default_factory=dict)


def _verify_token(
    token: Annotated[str | None, Header(alias="X-Internal-Token")] = None,
) -> None:
    from xnch.config import settings

    expected = settings.memory_service_token
    if not expected:
        # Fail CLOSED: unconfigured token = loud misconfiguration, never open access.
        raise HTTPException(status_code=503, detail="memory-service token not configured")
    if not token or not secrets.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="invalid internal token")


async def _build_real_stores() -> MemoryServiceStores:
    """Construct the real store set from settings (async, node-a)."""
    from xnch.config import settings
    from xnch.memory.graph_broadcaster import GraphBroadcaster
    from xnch.memory.graph_store import GraphStore
    from xnch.memory.pg_episodic_store import PgEpisodicStore
    from xnch.memory.relationship_store import RelationshipStore
    from xnch.memory.sensory_buffer import SensoryBuffer
    from xnch.memory.working_memory import WorkingMemory
    from scraper.pipeline.store import ScraperDocumentStore

    pg = PgEpisodicStore(settings.postgres_url)
    await pg.connect()
    rel = RelationshipStore(settings.postgres_url)
    await rel.connect()
    broadcaster = GraphBroadcaster()
    broadcaster.bind_loop(asyncio.get_running_loop())
    graph = GraphStore(
        db_path=settings.db_path,
        relationship_store=rel,
        broadcaster=broadcaster,
    )
    graph.connect()
    return MemoryServiceStores(
        pg_episodic=pg,
        graph_store=graph,
        relationship_store=rel,
        working_memory=WorkingMemory(settings.redis_url),
        sensory_buffer=SensoryBuffer(settings.redis_url),
        scraped_store=ScraperDocumentStore(pg._pool),
        broadcaster=broadcaster,
    )


async def _close_stores(stores: MemoryServiceStores) -> None:
    for name in ("working_memory", "sensory_buffer", "relationship_store", "pg_episodic"):
        obj = getattr(stores, name)
        closer = getattr(obj, "aclose", None) or getattr(obj, "close", None)
        if closer is not None:
            maybe = closer()
            if inspect.isawaitable(maybe):
                await maybe
    getattr(stores.graph_store, "close", lambda: None)()


def build_app(store_factory: Callable[[], MemoryServiceStores] | None = None) -> FastAPI:
    """Build the memory-service app.

    store_factory: injection point for tests (sync factory returning fakes).
    Production (no arg) builds real stores from settings inside the lifespan.
    When a factory is given, stores are set EAGERLY so ASGITransport-based
    tests (which never run the lifespan) see them — mirrors how existing
    xnch route tests inject app.state directly.
    """

    @asynccontextmanager
    async def _lifespan(app: FastAPI):
        if getattr(app.state, "stores", None) is None:
            app.state.stores = (
                store_factory() if store_factory is not None else await _build_real_stores()
            )
        yield
        await _close_stores(app.state.stores)

    app = FastAPI(title="xnch-memory", version="1.0.0", lifespan=_lifespan)

    if store_factory is not None:
        app.state.stores = store_factory()

    @app.post("/v1/call")
    async def call(
        body: CallRequest, _: None = Depends(_verify_token)
    ) -> dict[str, Any]:
        stores: MemoryServiceStores = app.state.stores
        if (body.store, body.method) not in _ALLOWED:
            raise HTTPException(
                status_code=403, detail=f"method not allowed: {body.store}.{body.method}"
            )
        target = getattr(stores, body.store, None)
        if target is None:
            raise HTTPException(status_code=404, detail=f"unknown store: {body.store}")
        fn = getattr(target, body.method, None)
        if not callable(fn):
            raise HTTPException(
                status_code=404, detail=f"unknown method: {body.store}.{body.method}"
            )
        result = fn(*body.args, **body.kwargs)
        if inspect.isawaitable(result):
            result = await result
        return {"result": result}

    return app
```

- [ ] **Step 4: Run tests**

Run: `pytest xnch/tests/test_memory_server.py -v`
Expected: 6 PASS

- [ ] **Step 5: Commit (inside xnch submodule)**

```bash
git -C xnch add xnch/memory/server.py xnch/tests/test_memory_server.py
git -C xnch commit -m "feat: memory-service app with whitelisted /v1/call dispatch"
```

---

### Task 4: Server — `/healthz`, `/v1/consolidation/run`, `/v1/graph/stream`, `__main__`

**Files:**
- Modify: `xnch/memory/server.py`
- Test: `xnch/tests/test_memory_server.py` (extend)

**Interfaces:**
- Consumes: `xnch.jobs.consolidation.run_consolidation(pg_episodic=..., relationship_store=..., graph_store=...)`, broadcaster API `subscribe()/unsubscribe(queue)`.
- Produces: `GET /healthz` → `{"status": "ok"|"degraded", "tiers": {"postgres": bool, "kuzu": bool}}`; `POST /v1/consolidation/run` → consolidation counts dict; `GET /v1/graph/stream` (SSE, token-gated); `python -m xnch.memory.server` entrypoint (`XNCH_MEMORY_BIND`/`XNCH_MEMORY_PORT`).

- [ ] **Step 1: Write the failing tests (append to test_memory_server.py)**

```python
async def test_healthz_reports_tiers(app) -> None:
    async with _client(app) as client:
        resp = await client.get("/healthz", headers={"X-Internal-Token": "sekrit"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in {"ok", "degraded"}
    assert "postgres" in body["tiers"] and "kuzu" in body["tiers"]


async def test_consolidation_run(monkeypatch: pytest.MonkeyPatch, app) -> None:
    from xnch.memory import server as srv

    async def fake_consolidate(**kwargs: Any) -> dict[str, int]:
        return {"triples_written": 2, "episodes_processed": 5,
                "extraction_failures": 0, "archived": 1}

    monkeypatch.setattr(srv, "run_consolidation", fake_consolidate)
    async with _client(app) as client:
        resp = await client.post(
            "/v1/consolidation/run", headers={"X-Internal-Token": "sekrit"}
        )
    assert resp.status_code == 200
    assert resp.json()["triples_written"] == 2


async def test_graph_stream_sse(app) -> None:
    async with _client(app) as client:
        async with client.stream(
            "GET", "/v1/graph/stream", headers={"X-Internal-Token": "sekrit"}
        ) as resp:
            assert resp.status_code == 200
            lines = []
            async for line in resp.aiter_lines():
                lines.append(line)
                if len(lines) >= 2:
                    break
    assert any(l.startswith("data:") for l in lines)
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest xnch/tests/test_memory_server.py -v` → new tests FAIL (404s).

- [ ] **Step 3: Implement (append inside `build_app`, after the `/v1/call` route)**

```python
    @app.get("/healthz")
    async def healthz(_: None = Depends(_verify_token)) -> dict[str, Any]:
        stores: MemoryServiceStores = app.state.stores
        tiers: dict[str, bool] = {}

        try:
            pool = getattr(stores.pg_episodic, "_pool", None)
            if pool is None:
                tiers["postgres"] = False
            else:
                await pool.fetchval("SELECT 1")
                tiers["postgres"] = True
        except Exception:
            tiers["postgres"] = False

        try:
            stats = stores.graph_store.get_stats()
            tiers["kuzu"] = "entity_count" in stats
        except Exception:
            tiers["kuzu"] = False

        ok = all(tiers.values())
        return {"status": "ok" if ok else "degraded", "tiers": tiers}

    @app.post("/v1/consolidation/run")
    async def consolidation_run(_: None = Depends(_verify_token)) -> dict[str, int]:
        stores: MemoryServiceStores = app.state.stores
        return await run_consolidation(
            pg_episodic=stores.pg_episodic,
            relationship_store=stores.relationship_store,
            graph_store=stores.graph_store,
        )

    @app.get("/v1/graph/stream")
    async def graph_stream(_: None = Depends(_verify_token)) -> StreamingResponse:
        import asyncio
        import json as _json

        stores: MemoryServiceStores = app.state.stores
        broadcaster = stores.broadcaster

        async def event_stream():
            stats = stores.graph_store.get_stats()
            yield f'data: {_json.dumps({"type": "stats", **stats}, default=str)}\n\n'
            yield 'data: {"type": "ready"}\n\n'
            queue = await broadcaster.subscribe()
            try:
                while True:
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=2.5)
                        yield f'data: {_json.dumps(event, default=str)}\n\n'
                    except asyncio.TimeoutError:
                        yield 'data: {"type": "heartbeat"}\n\n'
            finally:
                broadcaster.unsubscribe(queue)

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
```

And at module top of `server.py`:
```python
from fastapi.responses import StreamingResponse
from xnch.jobs.consolidation import run_consolidation
```
(Note: `run_consolidation` must be imported at module level so `monkeypatch.setattr(srv, "run_consolidation", ...)` works.)

Then `xnch/memory/__main__.py`… no — the entrypoint belongs to the server module. Append to `server.py`:

```python
def main() -> None:
    import os

    import uvicorn

    host = os.environ.get("XNCH_MEMORY_BIND", "127.0.0.1")
    port = int(os.environ.get("XNCH_MEMORY_PORT", "8003"))
    uvicorn.run(build_app(), host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests**

Run: `pytest xnch/tests/test_memory_server.py -v` → 9 PASS (healthz reports kuzu via fake graph; postgres tier False → status "degraded" — assert covers both).

- [ ] **Step 5: Commit (inside xnch submodule)**

```bash
git -C xnch add xnch/memory/server.py xnch/tests/test_memory_server.py
git -C xnch commit -m "feat: memory-service healthz, consolidation endpoint, graph SSE, entrypoint"
```

---

### Task 5: Client — `RemoteStoreRef` (async) + `RemoteGraphStore` (sync)

**Files:**
- Create: `xnch/memory/client.py`
- Test: `xnch/tests/test_memory_client.py` (new)

**Interfaces:**
- Consumes: `POST /v1/call` (Task 3), `Settings.memory_service_url`/`memory_service_token`.
- Produces:
  - `RemoteStoreRef(base_url: str, token: str, store: str, timeout: float = 10.0, transport: httpx.AsyncBaseTransport | None = None)` — `__getattr__` returns async callables forwarding to `/v1/call`.
  - `RemoteGraphStore(base_url: str, token: str, timeout: float = 5.0, transport: httpx.BaseTransport | None = None)` — `__getattr__` returns SYNC callables (blocking httpx) so existing gateway call sites (`store.get_stats()` etc.) need zero changes.
  - `MemoryServiceError(Exception)` — raised on non-2xx / transport failure (consumed by Task 7 degrade wrapper).

- [ ] **Step 1: Write the failing tests**

```python
"""Memory client: async refs, sync graph store, error mapping."""

from __future__ import annotations

import httpx
import pytest

from xnch.memory.client import (
    MemoryServiceError, RemoteGraphStore, RemoteStoreRef,
)


def _ok_handler(payload_out: dict) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        payload_out["path"] = request.url.path
        payload_out["body"] = request.read()
        return httpx.Response(200, json={"result": 42})
    return httpx.MockTransport(handler)


async def test_remote_ref_forwards_call() -> None:
    seen: dict = {}
    ref = RemoteStoreRef(
        "http://node-a:8003", token="t", store="pg_episodic",
        transport=_ok_handler(seen),
    )
    result = await ref.retrieve_similar(query_text="hi", top_k=3)
    assert result == 42
    assert seen["path"] == "/v1/call"
    import json

    body = json.loads(seen["body"])
    assert body == {
        "store": "pg_episodic", "method": "retrieve_similar",
        "args": [], "kwargs": {"query_text": "hi", "top_k": 3},
    }


async def test_remote_ref_error_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"detail": "method not allowed"})

    ref = RemoteStoreRef(
        "http://node-a:8003", token="t", store="pg_episodic",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(MemoryServiceError):
        await ref.execute("SELECT 1")


def test_remote_graph_store_sync_call() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        return httpx.Response(200, json={"result": {"entity_count": 7}})

    graph = RemoteGraphStore(
        "http://node-a:8003", token="t", transport=httpx.MockTransport(handler)
    )
    stats = graph.get_stats()  # sync — no await
    assert stats["entity_count"] == 7
    assert seen["path"] == "/v1/call"


def test_remote_graph_store_private_attrs_passthrough() -> None:
    graph = RemoteGraphStore("http://node-a:8003", token="t")
    assert graph._base_url == "http://node-a:8003"
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest xnch/tests/test_memory_client.py -v` → FAIL (module missing)

- [ ] **Step 3: Implement `xnch/memory/client.py` (part 1)**

```python
"""Gateway-side client for the memory service (remote mode)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_REPLAY_KEY = "xnch:memory:replay"


class MemoryServiceError(Exception):
    """Memory service call failed (non-2xx or transport error)."""


def _raise_for(resp: httpx.Response) -> None:
    if resp.status_code >= 400:
        raise MemoryServiceError(
            f"memory-service {resp.status_code}: {resp.text[:200]}"
        )


class RemoteStoreRef:
    """Async proxy: any attribute becomes an async call to POST /v1/call."""

    def __init__(
        self,
        base_url: str,
        token: str,
        store: str,
        timeout: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = {"X-Internal-Token": token} if token else {}
        self._store = store
        self._timeout = timeout
        self._transport = transport

    def __getattr__(self, method: str) -> Any:
        if method.startswith("_"):
            raise AttributeError(method)

        async def call(*args: Any, **kwargs: Any) -> Any:
            try:
                async with httpx.AsyncClient(
                    base_url=self._base_url,
                    timeout=self._timeout,
                    headers=self._headers,
                    transport=self._transport,
                ) as client:
                    resp = await client.post(
                        "/v1/call",
                        json={
                            "store": self._store,
                            "method": method,
                            "args": list(args),
                            "kwargs": kwargs,
                        },
                    )
            except httpx.HTTPError as exc:
                raise MemoryServiceError(f"memory-service unreachable: {exc}") from exc
            _raise_for(resp)
            return resp.json().get("result")

        return call


class RemoteGraphStore:
    """SYNC proxy for the Kuzu graph store — existing call sites are sync."""

    def __init__(
        self,
        base_url: str,
        token: str,
        timeout: float = 5.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = {"X-Internal-Token": token} if token else {}
        self._timeout = timeout
        self._transport = transport

    def __getattr__(self, method: str) -> Any:
        if method.startswith("_"):
            raise AttributeError(method)

        def call(*args: Any, **kwargs: Any) -> Any:
            try:
                with httpx.Client(
                    base_url=self._base_url,
                    timeout=self._timeout,
                    headers=self._headers,
                    transport=self._transport,
                ) as client:
                    resp = client.post(
                        "/v1/call",
                        json={
                            "store": "graph_store",
                            "method": method,
                            "args": list(args),
                            "kwargs": kwargs,
                        },
                    )
            except httpx.HTTPError as exc:
                raise MemoryServiceError(f"memory-service unreachable: {exc}") from exc
            _raise_for(resp)
            return resp.json().get("result")

        return call
```

- [ ] **Step 4: Run tests** → `pytest xnch/tests/test_memory_client.py -v` → 4 PASS

- [ ] **Step 5: Commit (inside xnch submodule)**

```bash
git -C xnch add xnch/memory/client.py xnch/tests/test_memory_client.py
git -C xnch commit -m "feat: memory-service client refs (async + sync graph proxy)"
```

---

### Task 6: Client — degrade wrapper + replay loop

**Files:**
- Modify: `xnch/memory/client.py`
- Test: `xnch/tests/test_memory_client.py` (extend)

**Interfaces:**
- Consumes: `RemoteStoreRef` (Task 5), a `redis.asyncio` client.
- Produces: `DegradingEpisodic(inner: RemoteStoreRef, redis: redis.asyncio.Redis)` — `retrieve_similar` returns `[]` + logs a warning on `MemoryServiceError` (chat continues without recall); `store_episode(type_, **kwargs)` queues to Redis list `xnch:memory:replay` and returns a synthetic id `replay:<uuid>`; all other methods pass through. `start_replay_loop(inner, redis, interval_s=30.0) -> asyncio.Task` — pops entries, replays via `inner.store_episode`, re-queues on failure.

- [ ] **Step 1: Write the failing tests (append)**

```python
async def test_degrade_retrieve_returns_empty_on_outage() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    inner = RemoteStoreRef(
        "http://node-a:8003", token="t", store="pg_episodic",
        transport=httpx.MockTransport(handler),
    )

    class _FakeRedis:
        async def lpush(self, *a: Any) -> int:
            return 1

    degraded = DegradingEpisodic(inner, _FakeRedis())
    assert await degraded.retrieve_similar(query_text="hi") == []


async def test_degrade_store_queues_replay() -> None:
    pushed: list = []

    class _FakeRedis:
        async def lpush(self, key: str, value: str) -> int:
            pushed.append((key, value))
            return 1

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    inner = RemoteStoreRef(
        "http://node-a:8003", token="t", store="pg_episodic",
        transport=httpx.MockTransport(handler),
    )
    degraded = DegradingEpisodic(inner, _FakeRedis())
    mem_id = await degraded.store_episode("note", raw_text="hello", importance=2.0)
    assert mem_id.startswith("replay:")
    assert pushed[0][0] == "xnch:memory:replay"
    import json

    assert json.loads(pushed[0][1]) == {
        "type_": "note", "raw_text": "hello", "importance": 2.0,
    }


async def test_replay_loop_requeues_on_failure() -> None:
    calls: list = []

    class _Inner:
        async def store_episode(self, **kwargs: Any) -> str:
            calls.append(kwargs)
            raise MemoryServiceError("still down")

    class _FakeRedis:
        def __init__(self) -> None:
            self.items = ['{"type_": "note", "raw_text": "x"}']

        async def lpop(self, key: str) -> str | None:
            return self.items.pop(0) if self.items else None

        async def rpush(self, key: str, value: str) -> int:
            self.items.append(value)
            return 1

    redis = _FakeRedis()
    task = asyncio.create_task(_replay_loop(_Inner(), redis, interval_s=0.05))
    await asyncio.sleep(0.2)
    task.cancel()
    assert len(calls) >= 1
    assert redis.items  # re-queued
```

(Add `import asyncio` and the `DegradingEpisodic, _replay_loop` imports to the test file header.)

- [ ] **Step 2: Run to verify failure** → FAIL (names not defined)

- [ ] **Step 3: Implement (append to `xnch/memory/client.py`)**

```python
class DegradingEpisodic:
    """Remote pg_episodic that survives outages: reads degrade, writes replay."""

    def __init__(self, inner: RemoteStoreRef, redis: Any) -> None:
        self._inner = inner
        self._redis = redis

    async def retrieve_similar(self, **kwargs: Any) -> list[dict[str, Any]]:
        try:
            return await self._inner.retrieve_similar(**kwargs)
        except MemoryServiceError as exc:
            logger.warning("memory-service recall degraded: %s", exc)
            return []

    async def store_episode(self, type_: str, **kwargs: Any) -> str:
        import json as _json
        from uuid import uuid4

        try:
            return await self._inner.store_episode(type_, **kwargs)
        except MemoryServiceError as exc:
            logger.warning("memory-service write queued for replay: %s", exc)
            payload = _json.dumps({"type_": type_, **kwargs})
            await self._redis.lpush(_REPLAY_KEY, payload)
            return f"replay:{uuid4()}"

    def __getattr__(self, method: str) -> Any:
        if method.startswith("_"):
            raise AttributeError(method)
        return getattr(self._inner, method)


async def _replay_loop(inner: Any, redis: Any, interval_s: float = 30.0) -> None:
    import json as _json

    while True:
        await asyncio.sleep(interval_s)
        raw = await redis.lpop(_REPLAY_KEY)
        while raw:
            try:
                payload = _json.loads(raw)
                await inner.store_episode(**payload)
            except Exception as exc:
                logger.warning("memory replay failed, re-queued: %s", exc)
                await redis.rpush(_REPLAY_KEY, raw)
                break
            raw = await redis.lpop(_REPLAY_KEY)
```

(Add `import asyncio` at module top.)

- [ ] **Step 4: Run tests** → `pytest xnch/tests/test_memory_client.py -v` → 7 PASS

- [ ] **Step 5: Commit (inside xnch submodule)**

```bash
git -C xnch add xnch/memory/client.py xnch/tests/test_memory_client.py
git -C xnch commit -m "feat: memory client degrade path (recall fallback + write replay)"
```

---

### Task 7: Bootstrap — `build_memory()` (embedded | remote)

**Files:**
- Create: `xnch/memory/bootstrap.py`
- Test: `xnch/tests/test_memory_bootstrap.py` (new)

**Interfaces:**
- Consumes: current store construction from `xnch/main.py:88-115` (embedded branch must be behavior-identical: PgEpisodicStore+connect, ScraperDocumentStore(pg._pool), SensoryBuffer, WorkingMemory, GraphBroadcaster+bind_loop, RelationshipStore+connect, GraphStore+connect); `RemoteStoreRef`, `RemoteGraphStore`, `DegradingEpisodic`, `_replay_loop` (Tasks 5-6).
- Produces: `MemoryBackends` dataclass with fields `pg_episodic, graph_store, relationship_store, working_memory, sensory_buffer, scraped_store, graph_broadcaster` (graph_broadcaster `None` in remote mode — drives the SSE relay branch in Task 9), plus `async def aclose()` (embedded: closes stores as `xnch/main.py:284-288` does today; remote: cancels the replay task). `async def build_memory(settings) -> MemoryBackends`.

- [ ] **Step 1: Write the failing tests**

```python
"""build_memory: embedded default vs remote refs."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import xnch.memory.bootstrap as bootstrap
from xnch.memory.bootstrap import build_memory


class _FakeRedis:
    async def ping(self) -> bool:
        return True


def _settings(embedded: bool) -> SimpleNamespace:
    return SimpleNamespace(
        memory_embedded=embedded,
        memory_service_url="http://127.0.0.1:8003",
        memory_service_token="t",
        postgres_url="postgresql://x",
        redis_url="redis://localhost:6379/0",
        db_path="/tmp/xnch.db",
    )


async def test_remote_builds_refs_without_stores(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*a: object, **k: object) -> object:
        raise AssertionError("remote mode must not construct embedded stores")

    monkeypatch.setattr(bootstrap, "PgEpisodicStore", boom)
    monkeypatch.setattr(bootstrap, "RelationshipStore", boom)
    monkeypatch.setattr(bootstrap, "GraphStore", boom)
    monkeypatch.setattr(bootstrap, "SensoryBuffer", boom)
    monkeypatch.setattr(bootstrap, "WorkingMemory", boom)
    monkeypatch.setattr(bootstrap, "GraphBroadcaster", boom)

    async def fake_redis_from_url(url: str) -> _FakeRedis:
        return _FakeRedis()

    monkeypatch.setattr(bootstrap, "redis_from_url", fake_redis_from_url)

    backends = await build_memory(_settings(embedded=False))

    from xnch.memory.client import DegradingEpisodic, RemoteGraphStore, RemoteStoreRef

    assert isinstance(backends.pg_episodic, DegradingEpisodic)
    assert isinstance(backends.graph_store, RemoteGraphStore)
    assert isinstance(backends.relationship_store, RemoteStoreRef)
    assert isinstance(backends.working_memory, RemoteStoreRef)
    assert isinstance(backends.sensory_buffer, RemoteStoreRef)
    assert isinstance(backends.scraped_store, RemoteStoreRef)
    assert backends.graph_broadcaster is None
    assert backends._embedded is False
    assert backends._replay_task is not None
    backends._replay_task.cancel()


class _AsyncStub:
    """Stands in for stores whose connect()/close() are awaited (pg, rel)."""

    def __init__(self, made: list[str], name: str) -> None:
        made.append(name)
        self._pool = object()

    async def connect(self) -> None:
        pass

    async def close(self) -> None:
        pass


class _SyncStub:
    """Stands in for sync-connecting stores (graph) + plain constructed ones."""

    def __init__(self, made: list[str], name: str) -> None:
        made.append(name)

    def connect(self) -> None:
        pass

    def close(self) -> None:
        pass

    def bind_loop(self, loop: object) -> None:
        pass

    async def aclose(self) -> None:
        pass


async def test_embedded_builds_real_stores(monkeypatch: pytest.MonkeyPatch) -> None:
    made: list[str] = []

    monkeypatch.setattr(bootstrap, "PgEpisodicStore", lambda url: _AsyncStub(made, "pg"))
    monkeypatch.setattr(bootstrap, "RelationshipStore", lambda url: _AsyncStub(made, "rel"))
    monkeypatch.setattr(bootstrap, "GraphStore", lambda **kw: _SyncStub(made, "graph"))
    monkeypatch.setattr(bootstrap, "SensoryBuffer", lambda url: _SyncStub(made, "sensory"))
    monkeypatch.setattr(bootstrap, "WorkingMemory", lambda url: _SyncStub(made, "working"))
    monkeypatch.setattr(bootstrap, "GraphBroadcaster", lambda: _SyncStub(made, "broadcaster"))

    class _ScraperStub:
        def __init__(self, pool: object) -> None:
            made.append("scraped")

    import sys

    fake_scraper_mod = SimpleNamespace(ScraperDocumentStore=_ScraperStub)
    monkeypatch.setitem(sys.modules, "scraper.pipeline.store", fake_scraper_mod)

    backends = await build_memory(_settings(embedded=True))
    # Construction order in _build_embedded:
    # pg, scraped, sensory, working, broadcaster, rel, graph
    assert made == ["pg", "scraped", "sensory", "working", "broadcaster", "rel", "graph"]
    assert backends.graph_broadcaster is not None
    assert backends._embedded is True
    await backends.aclose()  # all stub close paths exist
```

(The `from types import SimpleNamespace` import at the top of the test file provides `SimpleNamespace` used for the scraper module stub.)

(Use only these two tests; the first one should patch constructors the same way and assert `made == ["pg", "scraped", "sensory", "working", "rel", "graph"]` per the exact construction order in Step 3 — adjust the expected list to the final construction sequence.)

- [ ] **Step 2: Run to verify failure** → FAIL (module missing)

- [ ] **Step 3: Implement `xnch/memory/bootstrap.py`**

```python
"""Memory backend construction — embedded (in-process) or remote (memory-service)."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

import redis.asyncio as aioredis

from xnch.memory.client import DegradingEpisodic, RemoteGraphStore, RemoteStoreRef, _replay_loop
from xnch.memory.graph_broadcaster import GraphBroadcaster
from xnch.memory.graph_store import GraphStore
from xnch.memory.pg_episodic_store import PgEpisodicStore
from xnch.memory.relationship_store import RelationshipStore
from xnch.memory.sensory_buffer import SensoryBuffer
from xnch.memory.working_memory import WorkingMemory

logger = logging.getLogger(__name__)

redis_from_url = aioredis.from_url  # patch point for tests


@dataclass
class MemoryBackends:
    pg_episodic: Any
    graph_store: Any
    relationship_store: Any
    working_memory: Any
    sensory_buffer: Any
    scraped_store: Any
    graph_broadcaster: Any = None
    _replay_task: asyncio.Task | None = None
    _embedded: bool = True

    async def aclose(self) -> None:
        if self._replay_task is not None:
            self._replay_task.cancel()
        if not self._embedded:
            return
        await self.working_memory.aclose()
        await self.sensory_buffer.aclose()
        await self.relationship_store.close()
        await self.pg_episodic.close()
        self.graph_store.close()


async def build_memory(settings: Any) -> MemoryBackends:
    if settings.memory_embedded:
        return await _build_embedded(settings)
    return _build_remote(settings)


async def _build_embedded(settings: Any) -> MemoryBackends:
    from scraper.pipeline.store import ScraperDocumentStore

    pg = PgEpisodicStore(settings.postgres_url)
    await pg.connect()
    scraped = ScraperDocumentStore(pg._pool)
    sensory = SensoryBuffer(settings.redis_url)
    working = WorkingMemory(settings.redis_url)
    broadcaster = GraphBroadcaster()
    broadcaster.bind_loop(asyncio.get_running_loop())
    rel = RelationshipStore(settings.postgres_url)
    await rel.connect()
    graph = GraphStore(
        db_path=settings.db_path,
        relationship_store=rel,
        broadcaster=broadcaster,
    )
    graph.connect()
    return MemoryBackends(
        pg_episodic=pg,
        graph_store=graph,
        relationship_store=rel,
        working_memory=working,
        sensory_buffer=sensory,
        scraped_store=scraped,
        graph_broadcaster=broadcaster,
    )


def _build_remote(settings: Any) -> MemoryBackends:
    base = settings.memory_service_url
    token = settings.memory_service_token

    pg_ref = RemoteStoreRef(base, token, "pg_episodic")
    redis = redis_from_url(settings.redis_url)
    replay_task = asyncio.get_running_loop().create_task(
        _replay_loop(pg_ref, redis, interval_s=30.0)
    )
    return MemoryBackends(
        pg_episodic=DegradingEpisodic(pg_ref, redis),
        graph_store=RemoteGraphStore(base, token),
        relationship_store=RemoteStoreRef(base, token, "relationship_store"),
        working_memory=RemoteStoreRef(base, token, "working_memory"),
        sensory_buffer=RemoteStoreRef(base, token, "sensory_buffer"),
        scraped_store=RemoteStoreRef(base, token, "scraped_store"),
        graph_broadcaster=None,
        _replay_task=replay_task,
        _embedded=False,
    )
```

Note: the embedded construction is lifted verbatim from `xnch/main.py:88-115` — same order, same arguments — so behavior is bit-identical when `memory_embedded` is true.

- [ ] **Step 4: Run tests** → `pytest xnch/tests/test_memory_bootstrap.py -v` → 2 PASS (the embedded test patches constructors and asserts the sequence; the remote test asserts no constructor runs).

- [ ] **Step 5: Commit (inside xnch submodule)**

```bash
git -C xnch add xnch/memory/bootstrap.py xnch/tests/test_memory_bootstrap.py
git -C xnch commit -m "feat: build_memory bootstrap (embedded default, remote refs + replay)"
```

---

### Task 8: Gateway lifespan swap

**Files:**
- Modify: `xnch/main.py` (lines 88-115 construction block; lines 234-250 LangGraph block; lines 270-289 shutdown block)
- Test: existing suite must stay green (lifespan default is embedded — no behavioral change); no new test file needed beyond Task 7's.

**Interfaces:**
- Consumes: `build_memory` (Task 7).
- Produces: `app.state.memory` (MemoryBackends) plus the same `app.state.pg_episodic` etc. attributes as today — all consumers (routes, jobs kwargs, xnch_mcp handlers via `app.pg_episodic`) unchanged.

- [ ] **Step 1: Replace the memory construction block (lines 88-115)**

Replace everything from `    # PG episodic store (production backend)` through `    s.graph_store.connect()` (lines 88-115) with:

```python
    # Memory backends — embedded stores or memory-service refs (Phase 2)
    from .memory.bootstrap import build_memory

    s.memory = await build_memory(settings)
    s.pg_episodic = s.memory.pg_episodic
    s.scraped_store = s.memory.scraped_store
    s.sensory_buffer = s.memory.sensory_buffer
    s.working_memory = s.memory.working_memory
    s.relationship_store = s.memory.relationship_store
    s.graph_store = s.memory.graph_store
    s.graph_broadcaster = s.memory.graph_broadcaster
```

Check: the `sync_identity_memories(s.pg_episodic)` call at line 146 now receives either the real store or the degrading wrapper — both expose `fetch_by_type`/`store_episode`. `DeepHealthRunner` at line 256 uses `getattr(s.pg_episodic, "_pool", None)` — remote refs have no `_pool`, so the postgres probe is skipped automatically in remote mode (documented trade-off: postgres/kuzu visibility moves to the memory-service `/healthz` + Prometheus scrape, Task 9).

- [ ] **Step 2: Guard the LangGraph pipeline (lines 234-250)**

Change:

```python
    s.pipeline_runtime = None
    if settings.langgraph_pipeline:
```
to:
```python
    s.pipeline_runtime = None
    if settings.langgraph_pipeline and settings.memory_embedded:
        ...  # unchanged body
    elif settings.langgraph_pipeline:
        logger.warning(
            "langgraph_pipeline requires XNCH_MEMORY_EMBEDDED=1 (raw store access); "
            "pipeline disabled in remote memory mode"
        )
```

- [ ] **Step 3: Replace the shutdown block (lines 284-288)**

Replace:
```python
    await s.kv_cache.aclose()
    await s.sensory_buffer.aclose()
    await s.working_memory.aclose()
    await s.relationship_store.close()
    await s.pg_episodic.close()
```
with:
```python
    await s.kv_cache.aclose()
    await s.memory.aclose()
```

(`MemoryBackends.aclose()` closes exactly what the old lines closed in embedded mode, and cancels the replay task in remote mode.)

- [ ] **Step 4: Run the full suite**

Run: `pytest --tb=short -q`
Expected: green — default settings keep `memory_embedded=True`, so the lifespan constructs the same stores as before. Any failure indicates the embedded branch drifted from the original construction — fix before committing.

- [ ] **Step 5: Commit (inside xnch submodule)**

```bash
git -C xnch add xnch/main.py
git -C xnch commit -m "feat: gateway lifespan delegates to build_memory (embedded default)"
```

---

### Task 9: Graph SSE relay + infra + runbook

**Files:**
- Modify: `xnch/routes/memory.py` (`graph_stream`, line ~259), `infra/no-k3s/node-a/systemd/consolidation.service`
- Create: `infra/no-k3s/node-a/systemd/xnch-memory.service`, `docs/runbooks/memory-service-deploy.md`, and edit `docs/reference/env-vars.md`

**Interfaces:**
- Consumes: `settings.memory_service_url`/`memory_service_token`, `app.state.graph_broadcaster is None` as the remote-mode signal (Task 7).
- Produces: `/graph/stream` working identically for web UI in both modes; deployable `xnch-memory.service`; consolidated timer hitting the service.

- [ ] **Step 1: Add the relay branch to `graph_stream` in `xnch/routes/memory.py`**

At the top of the function body (after `app = request.app.state`):

```python
    if getattr(app, "graph_broadcaster", None) is None:
        # Remote memory mode: relay the memory-service SSE stream.
        import httpx

        from xnch.config import settings

        headers = {}
        if settings.memory_service_token:
            headers["X-Internal-Token"] = settings.memory_service_token

        async def relay() -> AsyncIterator[bytes]:
            timeout = httpx.Timeout(10.0, read=None)
            async with httpx.AsyncClient(
                base_url=settings.memory_service_url, timeout=timeout, headers=headers
            ) as client:
                async with client.stream("GET", "/v1/graph/stream") as resp:
                    resp.raise_for_status()
                    async for chunk in resp.aiter_bytes():
                        yield chunk

        return StreamingResponse(
            relay(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
```

(Import `AsyncIterator` from `collections.abc` and `StreamingResponse` is already imported in this module; if not, add it.)

- [ ] **Step 2: Create the systemd unit**

`infra/no-k3s/node-a/systemd/xnch-memory.service`:
```ini
[Unit]
Description=XNCH Memory Service — L0-L3 stores (node-a)
After=network.target postgres.service redis.service

[Service]
Type=simple
User=x-nch
WorkingDirectory=/home/x-nch/xnchSystems
EnvironmentFile=/home/x-nch/.xnch/xnch.env
Environment=PYTHONPATH=/home/x-nch/xnchSystems:/home/x-nch/xnchSystems/xnch
Environment=XNCH_MEMORY_BIND=0.0.0.0
Environment=XNCH_MEMORY_PORT=8003
ExecStart=/home/x-nch/xnchSystems/nexi/.venv/bin/python -m xnch.memory.server
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 3: Retarget the consolidation timer**

In `infra/no-k3s/node-a/systemd/consolidation.service`, change the ExecStart to hit the memory-service (token comes from the EnvironmentFile):

```ini
ExecStart=/bin/sh -c 'curl -sf -X POST -H "X-Internal-Token: $XNCH_MEMORY_TOKEN" http://127.0.0.1:8003/v1/consolidation/run'
```
(Add `EnvironmentFile=/home/x-nch/.xnch/xnch.env` if not present.)

- [ ] **Step 4: Write the runbook**

`docs/runbooks/memory-service-deploy.md`:
```markdown
# Memory service deploy (node-a)

## Preconditions
- Phase 2 code merged; `ss -ltn | grep 8003` empty on node-a.
- `XNCH_MEMORY_TOKEN` set in `/home/x-nch/.xnch/xnch.env` (same file the unit reads).
- LangGraph pipeline OFF or accept that it is skipped in remote mode.

## Deploy
1. Install the unit:
   ```
   sudo cp infra/no-k3s/node-a/systemd/xnch-memory.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now xnch-memory
   curl -s -H "X-Internal-Token: $XNCH_MEMORY_TOKEN" http://127.0.0.1:8003/healthz
   # {"status":"ok","tiers":{"postgres":true,"kuzu":true}}
   ```
2. Flip the gateway (node-a `~/.xnch/xnch.env`):
   ```
   XNCH_MEMORY_EMBEDDED=false
   XNCH_MEMORY_SERVICE_URL=http://127.0.0.1:8003
   XNCH_MEMORY_TOKEN=<same token>
   ```
   `sudo systemctl restart xnch`
3. Verify: `python -m clients.cli mcp test --skip-chat` (recall + store tools pass);
   web UI graph page streams (`/graph/stream` relay); chat works with recall.
4. Consolidation: confirm the timer's next fire lands in `journalctl -u xnch-memory`
   (POST /v1/consolidation/run, 200).
5. Prometheus: add a scrape job for `192.168.50.1:8003` (the service exposes
   FastAPI metrics via the same middleware pattern the gateway uses — if the
   metrics middleware is not yet wired into `build_app`, wire it the same way
   `xnch/main.py:294-296` does `install_metrics_middleware`, then reload Prometheus).

## Rollback (instant)
- Set `XNCH_MEMORY_EMBEDDED=true` (or remove the line) in `~/.xnch/xnch.env`,
  `sudo systemctl restart xnch`. The gateway reconstructs embedded stores.
- The service can keep running (it owns Kuzu only while the gateway is in remote
  mode; in embedded mode the GATEWAY owns the Kuzu file — stop one before the other:
  when rolling back, stop `xnch-memory` first if both would open the same Kuzu file).

## Invariants
- Exactly ONE process may own the Kuzu file (`~/.xnch/graph.kuzu` or db_path-derived
  location): embedded gateway OR memory-service — never both. The embedded/remote
  switch guarantees this by construction.
- `am_*` tools (agentmemory) are unaffected — this service covers xnch L0-L3 only.
```

- [ ] **Step 5: Update `docs/reference/env-vars.md`**

Add a "Memory service" table: `XNCH_MEMORY_EMBEDDED` (`true`), `XNCH_MEMORY_SERVICE_URL` (`http://127.0.0.1:8003`), `XNCH_MEMORY_TOKEN` (`""`), `XNCH_MEMORY_BIND`/`XNCH_MEMORY_PORT` (server side).

- [ ] **Step 6: Run full suite + commit**

Run: `pytest --tb=short -q` → green.

```bash
git add xnch/ infra/no-k3s/node-a/systemd/ docs/runbooks/memory-service-deploy.md docs/reference/env-vars.md
git commit -m "feat(memory-service): gateway SSE relay, systemd unit, consolidation retarget, runbook"
```
(xnch/ here stages the submodule gitlink — only after Task 10's final push, or bump incrementally if the submodule work is already pushed.)

- [ ] **Step 7: USER OPS GATE — cutover on node-a**

Operator runs `docs/runbooks/memory-service-deploy.md` end-to-end (deploy service → flip gateway → verify chat/web/runner → confirm consolidation). Do not mark Phase 2 complete until verified.

---

### Task 10: Final verification + submodule bump + spec status

- [ ] **Step 1: Full suite**

Run: `pytest --tb=short -q` → green, including `xnch/tests/test_memory_*.py` (server, client, bootstrap, settings) and `xnch_mcp/tests/test_registry.py` (tool registry unchanged).

- [ ] **Step 2: Remote-mode smoke (local, no deploy)**

Run:
```bash
XNCH_MEMORY_EMBEDDED=false XNCH_MEMORY_SERVICE_URL=http://127.0.0.1:9999 \
  .venv/bin/python -c "
import asyncio
from xnch.memory.client import RemoteStoreRef, MemoryServiceError
async def main():
    ref = RemoteStoreRef('http://127.0.0.1:9999', '', 'pg_episodic')
    try:
        await ref.retrieve_similar(query_text='x')
    except MemoryServiceError as e:
        print('OK:', e)
asyncio.run(main())"
```
Expected: `OK: memory-service unreachable: ...` (proves the failure path without a service).

- [ ] **Step 3: Push submodule + bump superrepo gitlink**

```bash
git -C xnch push
git add xnch
git commit -m "chore(xnch): bump to memory-service extraction (embedded default)"
```

- [ ] **Step 4: Update spec status**

In `docs/superpowers/specs/2026-09-11-micro-component-split.md`, mark Phase 2 (T2.1–T2.6) complete with the date; move Open Question 3 (full code move, option a) to "deferred — boundary proving". Commit:
```bash
git add docs/superpowers/specs/2026-09-11-micro-component-split.md
git commit -m "docs: mark Phase 2 of micro-component split complete"
```

---

## Risks & Mitigations (Phase 2 specific)

| Risk | Mitigation |
|---|---|
| Recall latency through HTTP boundary hurts chat | degrade wrapper returns `[]` on outage; 10s client timeout; `XNCH_MEMORY_EMBEDDED` instant rollback; post-cutover latency check in runbook verify step |
| Two processes open the Kuzu file simultaneously | embedded/remote switch owns Kuzu by construction; runbook "Invariants" section + rollback ordering rule |
| Sync graph proxy blocks the gateway event loop | LAN calls, ~ms, low-frequency graph endpoints only; 5s timeout; hot chat path never calls graph methods |
| Generic `/v1/call` becomes a security hole | strict (store, method) whitelist (Task 3 tests 403 on non-whitelisted), fail-closed token, internal bind |
| LangGraph pipeline breaks in remote mode | lifespan guard (Task 8 Step 2) — disabled with warning, documented in runbook |
| Replay queue grows unbounded during long outage | replay interval 30s, re-queue on failure; runbook rollback restores direct writes; dead-lettering beyond scope — monitor list length via Redis |
| `sync_identity_memories`/jobs get the wrapper | wrapper passes through all non-degraded methods via `__getattr__` (Task 6) |

## Phase 2 does NOT include (by design)

- Moving `xnch/memory` code out of the submodule (spec option a) — deferred until the HTTP boundary proves stable in prod for one consolidation cycle (spec Open Question 3).
- SQLite-backed stores (goal, workflow, agent_run, pattern, experience) — control-plane state, stays in gateway.
- `kv_cache` (Redis) — stays in gateway; not a memory tier.
- DeepHealth postgres/kuzu probes in remote mode — visibility moves to memory-service `/healthz` + Prometheus scrape (add scrape job when deploying, Task 9 Step 2 note).
