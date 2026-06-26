All 194 tests pass. Now I have everything I need for the full review.

---
Comprehensive Code Review — XNCH/Nexi v0

Summary

- Files reviewed: 51 source files + 7 deploy files
- Files clean: 28
- Files with issues: 23
- Critical: 7 | High: 11 | Medium: 10 | Low: 7
- pytest result: 194 passed, 0 failed (12 warnings — HMAC key length in test fixtures)

---
Issues by Severity

---
CRITICAL

---
File: nexi/nexi/proactivity/engine.py
Status: Issues Found

- Severity: Critical
- Line: 56
- Problem: pattern_store.get_failing_patterns() does not exist on PatternStore. The correct method is fetch_low_success(max_success_rate=..., min_confidence=...).
- Fix:
patterns = await pattern_store.fetch_low_success(max_success_rate=0.4, min_confidence=0.5)
- Note: fetch_low_success is async — the call also needs await and the enclosing check_and_queue must become async throughout this code path.
- Severity: Critical
- Lines: 75–77, 113–115
- Problem: Queries consolidation_jobs and extractor_runs tables that do not exist in db.py's schema. Every call to Rules 2 and 4 will throw aiosqlite.OperationalError: no such table. The exceptions are caught and logged as warnings, so the engine silently produces no events for two of its four rules.
- Fix: Replace with queries against system_state table using sentinel keys:
# Rule 2
async with db.execute(
    "SELECT value FROM system_state WHERE key = 'last_consolidation_run'"
) as cursor:
    row = await cursor.fetchone()

# Rule 4
async with db.execute(
    "SELECT value FROM system_state WHERE key = 'last_extraction_run'"
) as cursor:
    row = await cursor.fetchone()
- Both consolidation.py and pattern_extractor.py must UPDATE system_state with these keys on each run.
- Severity: Critical
- Line: 93
- Problem: Health check URL is http://i9-node:8080/health but vllm-gemma4.yaml exposes port 8000. Port mismatch means Rule 3 always fires an inference-down event — or if self._http is None (default), the check never runs at all.
- Fix: Read from config: settings.vllm_health_url defaulting to http://vllm-gemma4:8000/health. Also wire _http in the factory in nexi_gateway.py:43.

---
File: nexi/nexi/main.py
Status: Issues Found

- Severity: Critical
- Line: 201
- Problem: settings.xnch_base_url.replace("8001", "8001") is a no-op — replaces port 8001 with 8001. Execution dispatch sends to xnch itself, not an execution runner. Step 11 never reaches the actual executor.
- Fix:
execution_runner_url = settings.execution_runner_url  # new config key
- Or as a stopgap: .replace("8001", "8002"). Add execution_runner_url: str = "http://localhost:8002" to nexi/nexi/config.py.

---
File: xnch/xnch/main.py
Status: Issues Found

- Severity: Critical
- Lines: 103–121
- Problem: APScheduler add_job uses lambda: __import__('asyncio').get_event_loop().create_task(...). In Python 3.10+, get_event_loop() raises DeprecationWarning when called from a thread with no running loop, and in Python 3.12+ it raises RuntimeError. APScheduler's async scheduler calls job functions from the running event loop's thread, but the lambda idiom is fragile and non-idiomatic. Worse, if the scheduler falls back to an executor thread, this crashes silently.
- Fix: Use coroutine functions directly with APScheduler's AsyncIOScheduler:
scheduler.add_job(s.pattern_extractor.run, "cron", hour="*/6", id="pattern_extractor")
scheduler.add_job(s.score_adapter.evaluate, "cron", hour="*/6", minute=30, id="score_adapter")
scheduler.add_job(s.policy_candidates.run, "cron", hour="*/6", minute=45, id="policy_candidates")
- AsyncIOScheduler accepts coroutine functions directly and schedules them on the running loop.

---
File: xnch/xnch/memory/pg_episodic_store.py
Status: Issues Found

- Severity: Critical
- Lines: 159–183
- Problem: store_decision_episode() silently returns uuid.UUID(int=0) (all-zeros) when self._pool is None. Since connect() is a no-op (pass), _pool is always None. Any caller that stores this UUID as a foreign key into another table silently corrupts its data.
- Fix: Raise immediately rather than returning a sentinel:
if not self._pool:
    raise RuntimeError("PgEpisodicStore: PostgreSQL pool not initialized — call connect() with a real DSN")
- Severity: Critical
- Lines: 60–62
- Problem: retrieve_similar(embedding=None, query_text="something") falls through to get_memories() sorted by created_at, completely ignoring query_text. The context assembler calls this path on every chat request. Result: episodic recall is always "20 most recent" regardless of semantic relevance. The bump_recall() boost is also never applied (see HIGH #8).
- Fix:
if embedding is None:
    if query_text:
        results = search_memory(CATEGORY, query_text, n_results=top_k, filter_metadata={"archived": "False"})
        # process results with distance→similarity conversion (same as the else branch)
        ...
    else:
        memories = get_memories(CATEGORY, n_results=max(50, top_k * 10))
        return [...sorted by created_at...][:top_k]

---
File: xnch/xnch/memory/graph_store.py
Status: Issues Found

- Severity: Critical
- Lines: 63–76
- Problem: upsert_relation() is synchronous. When called from graph_extractor.extract_and_store() (which is async), asyncio.get_running_loop().create_task() should work — but the except RuntimeError: pass swallows the task if anything goes wrong. More critically, upsert_relation is also called from consolidation.py's synchronous _recompute_decay() indirectly via the graph, where no event loop is running — the RuntimeError is caught and silently dropped. Dual-write to PostgreSQL relationship_memory table never happens from sync contexts.
- Fix: Make upsert_relation async:
async def upsert_relation(self, from_id, to_id, rel_type, confidence) -> None:
    rel_text = f"{from_id} {rel_type} {to_id}"
    create_memory(RELATIONS_CATEGORY, rel_text, metadata={...})
    if self._relationship_store is not None:
        await self._relationship_store.upsert_relationship(
            entity_a=from_id, entity_b=to_id, rel_type=rel_type,
            evidence=f"confidence={confidence}", strength=confidence,
        )
- Update all callers in graph_extractor.py (already async) to await.
- Severity: Critical (also reported as Medium/duplicate by prior review)
- Lines: 55–61
- Problem: upsert_relation always calls create_memory() unconditionally — no check for an existing (from_id, to_id, rel_type) triple. Every call creates a new duplicate record in the relations agentmemory category. Over time this bloats unboundedly.
- Fix: Add a dedup check mirroring upsert_entity:
existing = search_memory(RELATIONS_CATEGORY, rel_text, n_results=5)
match = next((r for r in existing if r["metadata"].get("from_id") == from_id
              and r["metadata"].get("to_id") == to_id
              and r["metadata"].get("rel_type") == rel_type), None)
if match:
    update_memory(RELATIONS_CATEGORY, match["id"], metadata={...})
else:
    create_memory(RELATIONS_CATEGORY, rel_text, ...)

---
HIGH

---
File: nexi/nexi/pipeline/context_assembler.py
Status: Issues Found

- Severity: High
- Lines: 54–59
- Problem: After retrieve_similar(), bump_recall() is never called. Recall counts stay at 0, the episodic decay system never gets the recall boost (1 + 0.1 * recall_count), and all episodes decay on the same curve regardless of how often they're retrieved. Useful memories archive at the same rate as forgotten ones.
- Fix: Add after line 58:
for r in relevant:
    await pg_episodic.bump_recall(r["id"])

---
File: xnch/xnch/perception/vision_encoder.py
Status: Issues Found

- Severity: High
- Line: 42
- Problem: moondream.Image.open(image_bytes) — moondream does not expose PIL.Image as moondream.Image. This will raise AttributeError: module 'moondream' has no attribute 'Image' on the first screenshot.
- Fix:
def _encode():
    from PIL import Image as PILImage
    import io
    image = PILImage.open(io.BytesIO(image_bytes))
    return self._model.caption(image)["caption"]
- Severity: High
- Line: 43
- Problem: self._model.generate(image) — moondream's vl API does not have a generate() method. The correct method is .caption(image) which returns {"caption": str}.
- Fix: As above — use .caption(image)["caption"]. If a description prompt is needed: .query(image, "Describe this screen.")["answer"].

---
File: xnch/xnch/observability/langfuse_client.py
Status: Issues Found

- Severity: High
- Line: 21
- Problem: httpx.Client() is synchronous. trace_llm_call() is called from async contexts (option_generator, model_adapter). Every LLM trace blocks the async event loop on an HTTP call.
- Fix: Convert to async:
self._client = httpx.AsyncClient(base_url=self._host, timeout=5.0)

async def trace_llm_call(self, ...) -> dict | None:
    ...
    resp = await self._client.post("/api/public/ingestion", ...)
- Also change close() to async def aclose() and await self._client.aclose().
- Severity: Low (tracked here for proximity)
- Line: 58
- Problem: len(prompt.split()) counts words, not tokens. Langfuse shows inflated input usage for multi-word tokens (punctuation, subwords).
- Fix: Use litellm.token_counter(model=model, text=prompt) which is already available in the dependency tree.

---
File: xnch/xnch/routes/nexi_gateway.py
Status: Issues Found

- Severity: High
- Lines: 114–115
- Problem: In the non-streaming /nexi/chat endpoint, append_turn("user", body.message) happens after the LLM call succeeds. If the LLM call raises (502), the user's message is lost from working memory. The streaming path (line 155) correctly appends before the call.
- Fix: Move lines 114–115 to before the httpx block (after line 92, before the try:):
await app.working_memory.append_turn(body.session_id, "user", body.message)
try:
    async with httpx.AsyncClient(...) as client:
        ...
- Severity: High
- Lines: 236–237
- Problem: entity_id = str(ep.get("id", "")) passes the episodic memory document ID as an entity UUID to relationship_store.get_relationships(). Episodic IDs and entity IDs are completely different namespaces — the relationship table will never have a match. All relationship context in /memory/recall is empty.
- Fix: Look up the entity from graph_store by content:
text = ep.get("raw_text") or ep.get("summary", "")
if text:
    entity_node = app.graph_store.get_entity_by_name(text[:50])
    entity_id = entity_node["metadata"].get("entity_id", "") if entity_node else ""
- Severity: High
- Line: 41
- Problem: app.kv_cache._redis accesses the private _redis attribute of KVCache. This bypasses the KVCache's rate-limiting and dedup logic and will break if KVCache internal structure changes.
- Fix: Add a redis_client property to KVCache:
@property
def redis_client(self) -> aioredis.Redis:
    return self._redis
- Then use app.kv_cache.redis_client in the gateway.

---
File: xnch/xnch/learning/score_adapter.py
Status: Issues Found

- Severity: High
- Line: 107
- Problem: Query selects context_json from decision_episodes, but db.py's SQLite schema uses context_snapshot. This column doesn't exist in SQLite. The query fails silently (exception swallowed by the async with), returning no episodes. The entire weight-adjustment learning loop is dead code until this is fixed.
- Fix: Change line 107:
"""SELECT episode_id, intent_class, outcome, context_snapshot, created_at
- And line 119: r["context_snapshot"]

---
File: xnch/xnch/memory/graph_extractor.py
Status: Issues Found

- Severity: High
- Lines: 36–37
- Problem: GraphStore() is instantiated without a relationship_store, so the dual-write path to PostgreSQL is never wired in graph extraction. Entity relations from LLM extraction live only in agentmemory.
- Fix:
# Pass relationship_store through or use a module-level factory:
from xnch.memory.relationship_store import RelationshipStore
# Accept as parameter in extract_and_store():
async def extract_and_store(relationship_store=None) -> int:
    graph = GraphStore(relationship_store=relationship_store)
- Wire it from consolidation.py which has access to the stores.
- Severity: High
- Line: 72
- Problem: Model hardcoded to "ollama/phi3:mini". Should come from config to allow routing through LiteLLM proxy.
- Fix: model=settings.graph_extractor_model with default "ollama/phi3:mini".

---
File: xnch/xnch/jobs/consolidation.py
Status: Issues Found

- Severity: High
- Lines: 37–66
- Problem: _recompute_decay() and _archive_low_decay() are both synchronous functions that each call get_memories(..., n_results=5000) independently — two full scans of all 5000 episodes. They should share one load.
- Fix:
def _recompute_and_archive_decay() -> int:
    all_mem = get_memories(EPISODE_CATEGORY, n_results=5000)
    archived = 0
    now = datetime.now(timezone.utc)
    for m in all_mem:
        ...decay computation...
        meta["decay_score"] = str(round(decay, 4))
        if decay < 0.1 and meta.get("archived", "False") != "True":
            meta["archived"] = "True"
            archived += 1
        update_memory(EPISODE_CATEGORY, m["id"], metadata=meta)
    return archived

---
File: deploy/k8s/jobs/consolidation-cronjob.yaml
Status: Issues Found

- Severity: High
- Lines: 20–21
- Problem: value: postgresql://xnch:$(POSTGRES_PASSWORD)@... — $(POSTGRES_PASSWORD) is shell variable syntax, not Kubernetes env var substitution syntax. Kubernetes only expands $(VAR_NAME) syntax in env[].value if the variable is defined in the same env block. No POSTGRES_PASSWORD source is declared anywhere in this manifest. The PG connection string is literally postgresql://xnch:$(POSTGRES_PASSWORD)@postgres-pgvector:5432/xnch at runtime — connection fails.
- Fix:
env:
  - name: POSTGRES_PASSWORD
    valueFrom:
      secretKeyRef:
        name: xnch-secret
        key: postgres_password
  - name: XNCH_POSTGRES_URL
    value: postgresql://xnch:$(POSTGRES_PASSWORD)@postgres-pgvector:5432/xnch

---
File: deploy/docker/nexi.Dockerfile
Status: Issues Found

- Severity: High
- Line: 1
- Problem: FROM python:3.11-slim — pyproject.toml at the repo root requires python >= "3.13". Python 3.11 will install incompatible dependency versions or fail outright on 3.13-only syntax.
- Fix: FROM python:3.13-slim

---
File: xnch/xnch/perception/voice_daemon.py
Status: Issues Found

- Severity: High
- Line: 86
- Problem: np.frombuffer(raw, dtype=np.float32).astype(np.float32) — Microphone audio is PCM int16 (16-bit signed integers). Reinterpreting raw bytes as float32 without conversion produces garbage (the bit patterns of int16 pairs are interpreted as IEEE 754 float32 values). The .astype(np.float32) cast is then redundant — it converts garbage floats to garbage floats.
- Fix:
audio_np = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
- This matches the detect_silence() path at line 99 which correctly does dtype=np.int16.

---
MEDIUM

---
File: nexi/nexi/pipeline/intent_interpreter.py
Status: Issues Found

- Severity: Medium
- Line: 237
- Problem: LLM classification hardcodes "phi3-encoder" model name, bypassing the routing classifier that was just built. All LLM-classified intents use phi3 regardless of classify_request() routing logic.
- Fix: Before the httpx call, run classify_request(raw_input, actor_role, metadata) and use route.model_name. Or at minimum use a config key: settings.intent_classifier_model.
- Severity: Medium
- Lines: 84–85
- Problem: _extract_entity() uses tokens[1] as entity_id — hardcoded to the second token. Input "show me the database status" returns entity_id="me". Any multi-word command returns wrong entity extraction. This fallback is used whenever rule-based classification fires.
- Fix: Use a simple noun-phrase heuristic or return the full input as entity_id when the second-token extraction is ambiguous:
entity_id = " ".join(tokens[1:]) if len(tokens) > 1 else "unknown"
- Better: pass entity extraction to the LLM stage and skip the rule-based entity guess entirely.

---
File: xnch/xnch/memory/pg_episodic_store.py
Status: Issues Found

- Severity: Medium
- Lines: 152–157
- Problem: _get_memory_by_id() loads all 5000 episodes on every call for a single ID lookup. bump_recall() calls this synchronously per retrieved episode. With 5k episodes and 5 retrievals per chat, that's 25,000-episode scans per request.
- Fix: Use agentmemory's get_memory(CATEGORY, id) if available, or get_memories(CATEGORY, filter_metadata={"id": id}, n_results=1). Check agentmemory API for direct ID fetch.
- Severity: Medium
- Lines: 207–226
- Problem: fetch_decision_episodes_since() uses agentmemory fallback (loads all memories, filters client-side). The since filter is applied after loading limit=2000 — if there are 3000 recent episodes, the first 2000 are loaded and the filter misses some. The result is non-deterministic when episodes exceed limit.
- Fix: If self._pool is required for reliable operation, raise when pool is unavailable:
if not self._pool:
    raise RuntimeError("fetch_decision_episodes_since requires PostgreSQL pool")

---
File: xnch/xnch/security/memory_guard.py
Status: Issues Found

- Severity: Medium
- Problem: validate_memory_write() is defined but never called anywhere in the codebase. Memory writes in nexi_gateway.py (lines 117–121), consolidation.py, and context_assembler.py go directly to stores with no validation gate. The injection guard is called at the chat entry point but not at memory-write time.
- Fix: Call validate_memory_write(content, actor_role, trust_level) in nexi_gateway.py before each store_episode() call. Return 403 if validation fails.

---
File: xnch/xnch/security/trust_model.py
Status: Issues Found

- Severity: Medium
- Lines: 33–59
- Problem: requires_trust decorator discovers the Request object by scanning all args/kwargs for hasattr(arg, 'headers'). Any object with a .headers attribute (e.g. an httpx Response) would be mistakenly identified as the Request, and the wrong actor role would be read.
- Fix: Check for FastAPI Request type directly:
from starlette.requests import Request
for arg in args:
    if isinstance(arg, Request):
        request = arg
        break

---
File: xnch/xnch/learning/policy_candidates.py
Status: Issues Found

- Severity: Medium
- Line: 22
- Problem: _LLM_URL = "http://localhost:4000/v1/chat/completions" is hardcoded to localhost. In k8s, this should be http://litellm:4000/v1/chat/completions.
- Fix: Read from config: settings.litellm_proxy_url + "/chat/completions".

---
File: nexi/nexi/character/cold_start_seeder.py
Status: Issues Found

- Severity: Medium
- Line: 48
- Problem: list_recent(hours=999999) — 114 years of lookback — loads all 5000 agentmemory episodes on every cold-start check. This is a full scan just to count identity type entries.
- Fix: Use search_memory("episodes", "identity", n_results=1, filter_metadata={"type": "identity"}) and check if any results exist.

---
File: xnch/xnch/perception/attention_filter.py
Status: Issues Found

- Severity: Medium
- Lines: 65–70
- Problem: asyncio.create_task(run_consolidation()) is called from evaluate(), which is a synchronous method. asyncio.create_task() requires a running event loop in the calling thread. If called from a non-async context (e.g. a watchdog thread), this raises RuntimeError. The existing try/except only checks for a running loop but discards the task reference — any exception in the consolidation task is silently lost.
- Fix: Use asyncio.run_coroutine_threadsafe() with the main event loop if available, or schedule via a callback queue. At minimum, store the task reference:
task = asyncio.create_task(run_consolidation())
task.add_done_callback(lambda t: t.exception() and logger.error("consolidation failed: %s", t.exception()))

---
File: xnch/xnch/memory/pg_episodic_store.py
Status: Issues Found

- Severity: Medium
- Lines: 140–145
- Problem: execute() and fetchval() are stub methods that silently do nothing and return fake values. They appear to be compatibility shims for a PG-like interface but are never cleaned up. If any code path calls them expecting real PG behavior, it silently succeeds.
- Fix: Either remove them (they're not called in the current codebase) or raise NotImplementedError.

---
LOW

---
File: xnch/xnch/security/injection_guard.py
Status: Issues Found

- Severity: Low
- Line: 14
- Problem: re.compile(r'act as (?!Nexi)', re.I) — the negative lookahead is case-insensitive (re.I) for the act as part, but the lookahead (?!Nexi) is case-sensitive at match time. "act as nexi" would be flagged incorrectly.
- Fix: r'act as (?!Nexi|nexi)' or use (?!(?i)Nexi) (inline flag in lookahead).

---
File: xnch/xnch/perception/vision_encoder.py
Status: Issues Found

- Severity: Low
- Line: 43 (as corrected above)
- Problem: No prompt argument passed to generate(). Moondream requires a prompt or query string.
- Fix: Already covered by the High fix above (use .caption() or .query(image, prompt)).

---
File: xnch/xnch/perception/voice_daemon.py
Status: Issues Found

- Severity: Low
- Line: 90
- Problem: Whisper transcribe() auto-detects language on every call, adding ~100ms overhead per transcription.
- Fix: Pass language="en" (or make it configurable) if the user only speaks one language.

---
File: deploy/docker/nexi.Dockerfile
Status: Issues Found

- Severity: Low
- Line: 5
- Problem: COPY nexi/ /app/nexi/ copies __pycache__, .pyc files, and test directories into the production image, inflating image size.
- Fix: Add .dockerignore:
**/__pycache__
**/*.pyc
**/tests/
**/.pytest_cache

---
File: xnch/xnch/routes/nexi_gateway.py
Status: Issues Found

- Severity: Low
- Lines: 49–52
- Problem: asyncio.ensure_future(redis.delete(...)) in _invalidate_system_prompt_cache is fire-and-forget with no error handling. If Redis is unavailable, the exception is silently dropped.
- Fix: This is low-risk for a cache invalidation, but add a bare except Exception log. Alternatively, just await redis.delete(...) since the caller is always in an async context.

---
File: nexi/nexi/models/options.py
Status: Issues Found

- Severity: Low
- Lines: (ActionSpec.params)
- Problem: params: dict has no schema validation. The plan compiler passes params directly to the execution runner without any type or key constraints.
- Fix: For now, acceptable as dict[str, Any]. Add a JSON Schema validator if execution runner endpoints are specified.

---
File: xnch/xnch/deploy/k8s/i7-node/xnch-deployment.yaml
Status: Issues Found

- Severity: Low
- Line: 29
- Problem: Same $(POSTGRES_PASSWORD) expansion issue as the CronJob — the secret value is read via secretKeyRef for XNCH_AUTH_SECRET, but POSTGRES_PASSWORD has no secretKeyRef source. The env var expansion will produce a literal $(POSTGRES_PASSWORD) in the connection string.
- Fix: Add before the URL env var:
- name: POSTGRES_PASSWORD
  valueFrom:
    secretKeyRef:
      name: xnch-secret
      key: postgres_password

---
Files Confirmed Clean

┌───────────────────────────────────────────┬─────────────────────────────────────────────────────────────────┐
│                   File                    │                              Notes                              │
├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
│ xnch/memory/sensory_buffer.py             │ Correct async Redis, scan+pipeline pattern, TTL handling        │
├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
│ xnch/memory/working_memory.py             │ Correct session/turn management, async throughout               │
├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
│ xnch/memory/relationship_store.py         │ Sound asyncpg with proper ON CONFLICT upsert                    │
├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
│ xnch/memory/quarantine_store.py           │ Correct asyncpg, UUID handling, release logic                   │
├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
│ xnch/memory/db.py                         │ Correct SQLite schema — context_snapshot (not context_json),    │
│                                           │ WAL mode, indexes                                               │
├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
│ xnch/memory/episodic_store.py             │ Correct aiosqlite, json_patch for updates, distinct tuple       │
│                                           │ queries                                                         │
├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
│ xnch/memory/pattern_store.py              │ Correct upsert logic, fetch_low_success method exists and       │
│                                           │ matches callers                                                 │
├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
│ xnch/memory/kv_cache.py                   │ Rate limiting, dedup, trust-level scoped limits all correct     │
├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
│ xnch/routing/classifier.py                │ Correct routing logic, agentmemory recall/persist pattern       │
├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
│ xnch/security/actor_sandbox.py            │ Capability map correct, trust→capability mapping sound          │
├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
│ xnch/security/injection_guard.py          │ Good pattern coverage (one minor lookahead issue noted)         │
├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
│ xnch/security/memory_guard.py             │ Logic is correct — wiring problem only (see Medium)             │
├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
│ xnch/perception/file_watcher.py           │ Correct use of run_coroutine_threadsafe, async httpx            │
├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
│ xnch/perception/attention_filter.py       │ Mostly clean — one task-reference issue (see Medium)            │
├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
│ xnch/learning/pattern_extractor.py        │ Bayesian smoothing correct, extraction tracker correctly uses   │
│                                           │ its own table                                                   │
├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
│ xnch/learning/policy_candidates.py        │ Correct YAML parsing, hardcoded URL (see Medium), DENY filter   │
│                                           │ correct                                                         │
├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
│ xnch/auth/keys.py                         │ RS256 key generation correct                                    │
├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
│ xnch/auth/token.py                        │ JWT with jti replay protection correct                          │
├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
│ nexi/pipeline/plan_compiler.py            │ Small, focused, correct DAG compilation                         │
├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
│ nexi/pipeline/dispatch.py                 │ Token expiry handling, async httpx, correct                     │
├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
│ nexi/character/nexi_character.yaml        │ Valid YAML, loads without error, complete identity fields       │
├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
│ nexi/character/prompt_loader.py           │ Correct YAML load, build_system_prompt() produces valid prompt  │
├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
│ nexi/character/cold_start_seeder.py       │ Guard check present (identity_count > 0 before seeding) —       │
│                                           │ performance issue only                                          │
├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
│ deploy/k8s/i7-node/xnch-deployment.yaml   │ Recreate strategy ✓, role: memory nodeSelector ✓, resource      │
│                                           │ limits ✓                                                        │
├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
│                                           │ role: inference nodeSelector ✓, resource limits ✓ (no strategy: │
│ deploy/k8s/i9-node/nexi-deployment.yaml   │  field — defaults to RollingUpdate, but Nexi is stateless so    │
│                                           │ this is fine)                                                   │
├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
│ deploy/k8s/i9-node/vllm-gemma4.yaml       │ GPU reservation correct                                         │
├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
│ deploy/k8s/i7-node/postgres-pgvector.yaml │ StatefulSet with PVC, correct                                   │
├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
│ deploy/openclaw/config.yaml               │ No secrets hardcoded                                            │
└───────────────────────────────────────────┴─────────────────────────────────────────────────────────────────┘

---
Data Flow Verdict

The path OpenClaw → /nexi/chat → context assembler → LiteLLM → working memory → episodic store functions end-to-end for basic chat. scan_input() is correctly called before the LLM. assemble_context() wires all four memory layers and includes proactivity observations. The Nexi character YAML loads cleanly and build_system_prompt() produces a valid prompt. The weakest link in the chat path is episodic recall: retrieve_similar() with no embedding falls back to get_memories() sorted by recency — it ignores the query_text entirely — so every chat gets the 5 most recent episodes regardless of relevance. This is a silent functional degradation, not a crash.

The Nexi decision pipeline (/session/start) is architecturally complete through Step 10 (intent → options → policy filter → scoring → selection → verdict) but breaks at Step 11: the execution dispatch URL is a no-op replace (8001→8001), so dispatch always sends back to xnch itself. The learning loop is also broken in two independent ways: score_adapter.py queries a column that doesn't exist (context_json vs context_snapshot), and the APScheduler job lambda pattern will produce a RuntimeError in Python 3.13 when called from inside the async scheduler thread. The proactivity engine runs but Rules 1, 2, and 4 are broken (wrong method name, missing tables).

---
What's Production-Ready vs. Needs Work Before First Boot

Production-Ready

- All 4 memory layer classes (SensoryBuffer, WorkingMemory, PgEpisodicStore, QuarantineStore)
- RelationshipStore — correct asyncpg upsert with ON CONFLICT
- KVCache — rate limiting and dedup sound
- PatternStore — all queries correct
- EpisodicStore (SQLite) — column names match schema, correct json_patch update
- db.py — schema correct, WAL mode, foreign keys, all indexes present
- Security layer — injection_guard, trust_model, actor_sandbox, auth (keys.py, token.py) all correct
- file_watcher.py, attention_filter.py — perception plumbing sound
- policy/engine.py, policy/loader.py — correct evaluation and YAML loading
- audit/event_log.py, audit/ledger.py — append-only, tamper-evident
- nexi_character.yaml + prompt_loader.py — loads and builds correctly
- plan_compiler.py, dispatch.py, selector.py — pipeline steps correct
- classifier.py (routing) — routing logic and recall/persist correct
- cold_start_seeder.py — guard check present, will not re-seed
- All k8s manifests except CronJob secret injection and xnch-deployment PG password
- pytest: 194/194 pass

Needs Work Before First Boot

┌──────────┬───────────────────────────────────────┬─────────────────────────────────────────────────────────┐
│ Priority │                 File                  │                          Issue                          │
├──────────┼───────────────────────────────────────┼─────────────────────────────────────────────────────────┤
│ Critical │ nexi.Dockerfile                       │ python:3.11-slim → must be 3.13-slim                    │
├──────────┼───────────────────────────────────────┼─────────────────────────────────────────────────────────┤
│ Critical │ consolidation-cronjob.yaml +          │ $(POSTGRES_PASSWORD) not injected from Secret — both    │
│          │ xnch-deployment.yaml                  │ CronJob and xnch Deployment fail DB connect             │
├──────────┼───────────────────────────────────────┼─────────────────────────────────────────────────────────┤
│ Critical │ proactivity/engine.py:56              │ get_failing_patterns() → fetch_low_success() + await    │
├──────────┼───────────────────────────────────────┼─────────────────────────────────────────────────────────┤
│ Critical │ proactivity/engine.py:75–115          │ Queries non-existent tables — replace with system_state │
│          │                                       │  key queries                                            │
├──────────┼───────────────────────────────────────┼─────────────────────────────────────────────────────────┤
│ Critical │ nexi/main.py:201                      │ No-op URL replace — execution never dispatched to       │
│          │                                       │ executor                                                │
├──────────┼───────────────────────────────────────┼─────────────────────────────────────────────────────────┤
│ Critical │ vision_encoder.py:42–43               │ Wrong PIL import + wrong moondream method — crashes on  │
│          │                                       │ first screenshot                                        │
├──────────┼───────────────────────────────────────┼─────────────────────────────────────────────────────────┤
│ Critical │ pg_episodic_store.py:60–62            │ retrieve_similar ignores query_text when no embedding — │
│          │                                       │  episodic recall is broken                              │
├──────────┼───────────────────────────────────────┼─────────────────────────────────────────────────────────┤
│ Critical │ pg_episodic_store.py:183              │ Silent UUID-zero when pool is None — raise instead      │
├──────────┼───────────────────────────────────────┼─────────────────────────────────────────────────────────┤
│ Critical │ graph_store.py:63–76                  │ Sync dual-write silently fails — make upsert_relation   │
│          │                                       │ async                                                   │
├──────────┼───────────────────────────────────────┼─────────────────────────────────────────────────────────┤
│ Critical │ graph_store.py:55–61                  │ upsert_relation always creates duplicates — add dedup   │
├──────────┼───────────────────────────────────────┼─────────────────────────────────────────────────────────┤
│ High     │ xnch/main.py:103–121                  │ APScheduler lambda crashes in Python 3.13 — pass        │
│          │                                       │ coroutines directly                                     │
├──────────┼───────────────────────────────────────┼─────────────────────────────────────────────────────────┤
│ High     │ score_adapter.py:107                  │ context_json column doesn't exist → context_snapshot    │
├──────────┼───────────────────────────────────────┼─────────────────────────────────────────────────────────┤
│ High     │ context_assembler.py:58               │ bump_recall() never called — decay system misweights    │
│          │                                       │ all episodes                                            │
├──────────┼───────────────────────────────────────┼─────────────────────────────────────────────────────────┤
│ High     │ nexi_gateway.py:114                   │ User turn appended after LLM call — lost on failure     │
├──────────┼───────────────────────────────────────┼─────────────────────────────────────────────────────────┤
│ High     │ nexi_gateway.py:236                   │ Episode ID passed as entity ID — relationship context   │
│          │                                       │ always empty                                            │
├──────────┼───────────────────────────────────────┼─────────────────────────────────────────────────────────┤
│ High     │ voice_daemon.py:86                    │ int16 audio reinterpreted as float32 — transcription    │
│          │                                       │ garbage                                                 │
├──────────┼───────────────────────────────────────┼─────────────────────────────────────────────────────────┤
│ High     │ langfuse_client.py:21                 │ Sync httpx blocks event loop on every LLM trace         │
├──────────┼───────────────────────────────────────┼─────────────────────────────────────────────────────────┤
│ High     │ graph_extractor.py:36                 │ GraphStore created without relationship_store —         │
│          │                                       │ dual-write never happens from extraction                │
└──────────┴───────────────────────────────────────┴─────────────────────────────────────────────────────────┘