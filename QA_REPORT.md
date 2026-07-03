Architecture, Memory & Storage Gap Review

How the System Is Actually Wired (vs. What Was Intended)

The nominal flow is:
OpenClaw → xnch POST /session/init → nexi POST /session/start
  → intent → context → options → policy → score → select → compile → verdict → dispatch
  → execution-runner → xnch POST /execution/outcome → nexi POST /callback/outcome

None of the code is broken in isolation. The gaps are about what's not connected, what's parallel but isolated, and what's silently missing from the live path.

---
Critical Bugs (Silent Failures Today)

B1 — /nexi/chat does not exist
The gap report's test hit POST /nexi/chat and timed out. That route doesn't exist. The actual entry is POST /session/init on xnch (port 8001). Neither xnch nor nexi exposes a conversational {session_id, message} endpoint. OpenClaw is configured to call http://localhost:30800/v1 (the XNCH NodePort) — but with an OpenAI-compatible path, which also doesn't exist. The external API surface is completely unmapped.

B2 — Episodes are never created, so the learning loop is broken end-to-end
EpisodicStore.create_episode() is never called in the live request path. The verdict route (verdict.py) issues a token and writes to the DecisionLedger but never creates an episode. The execution outcome route (execution.py) calls complete_episode(decision_id=...) — which does SELECT episode_id FROM episodes WHERE decision_id = ? — but finds nothing because no row was ever inserted. It returns None. The Nexi callback then receives episode_id=None and skips the prediction write. Zero episodes are ever stored. The pattern extractor, score adapter, and policy candidate generator have nothing to work on. The entire learning loop is wired but dead.

B3 — run_early() is called but doesn't exist
xnch/xnch/routes/memory.py:103 calls app.pattern_extractor.run_early(). PatternExtractor only has .run(). This raises AttributeError inside asyncio.create_task(), which is swallowed silently — no crash, no log unless you specifically watch for task exceptions.

B4 — Execution runner URL points to a non-existent service
dispatch_execution() POSTs to settings.execution_runner_url (default http://localhost:8002). This service does not exist anywhere in the cluster or codebase. Every successful pipeline run ends with a connection error at dispatch. The nexi K8s manifest doesn't set NEXI_EXECUTION_RUNNER_URL. There is no execution runner deployment.

B5 — Prediction delta calculation is always 0.5 drift
nexi/nexi/main.py:239 reads outcome_score_predicted from the callback body. But xnch/xnch/routes/execution.py:_fire_nexi_callback never includes outcome_score_predicted in the payload it sends. So body.get("outcome_score_predicted", 0.5) always evaluates to 0.5, making every prediction delta |0.5 - actual|. The delta is meaningless noise, not a real prediction error signal.

B6 — xnch → nexi URL not set in K8s
xnch/xnch/config.py has nexi_base_url: str = "http://localhost:8000" with prefix XNCH_. The K8s deployment sets NEXI_XNCH_BASE_URL (nexi pointing to xnch) but does not set XNCH_NEXI_BASE_URL (xnch pointing to nexi). So when xnch tries to forward to nexi in session.py:83, it connects to localhost:8000 on the xnch pod — which is nothing.

B7 — STALE_SESSION with no retry path
The verdict route rejects with 409/STALE_SESSION if system_state_version changed since session start. Nexi handles TokenExpired with a retry, but has no retry for STALE_SESSION — it re-raises as a 409 to the caller. Under any concurrent request that triggers a state version increment, the session is permanently dead.

---
Architecture Gaps

A1 — The clarification flow is a 501 stub
POST /session/{session_id}/clarify in xnch returns HTTP 501 with the comment "Clarification re-entry not yet implemented in v0." When nexi raises ClarificationRequired, xnch returns CLARIFICATION_REQUIRED to the caller. There is no way for the user to submit the clarification and continue. The pipeline has an exit with no re-entry.

A2 — context_assembler.py is completely bypassed
nexi/nexi/pipeline/context_assembler.py:assemble_context() is a rich multi-source context builder: working memory turns, pgvector semantic search, graph entity connections, relationship graph, sensory buffer, proactivity engine. It is never called anywhere in the live pipeline. Instead context_loader.py makes a single HTTP call to xnch /memory/read which returns only recent episodes and patterns from SQLite. The rich context layer is built but wired to nothing.

A3 — XnchClient.start_session() is dead code
nexi/nexi/adapters/xnch_client.py:start_session() calls POST /session/start on xnch. That route doesn't exist in xnch (the route is /session/init). The actual flow is xnch calls nexi's /session/start, not the reverse. This method would 404 if invoked. It is never called in the current codebase.

A4 — plan_compiler is single-node only
compile_action_spec() always produces a CompiledDAG with exactly 1 node and 0 edges. Multi-step plans (backup → deploy, stage → promote) are architecturally impossible. The DAG model exists but the compiler never produces more than a single node.

A5 — _estimate_completion_ms always returns 30,000
nexi/nexi/main.py:281-284 — the function iterates manifest.episodes but does nothing with the values and unconditionally returns 30_000. Duration data is not stored in episodes at all (the _format_episode response in memory.py doesn't include duration_ms), so even if the logic were fixed it would have nothing to read.

A6 — Mem0 and Zep are deployed but have zero callers in code
Both are running as K8s services. Neither is imported, referenced, or called from any Python file in xnch/ or nexi/. They are infrastructure with no integration. The intent_interpreter uses agentmemory for intent recall, option_generator uses it for option persistence — but not mem0 or zep. The memory layer is partially covered by agentmemory but the dedicated long-term (mem0) and conversation-summary (zep) services are orphaned.

---
Memory & Storage Gaps

M1 — Two parallel episodic stores, never unified

The system has two completely separate episode stores that never communicate:

┌─────────────────┬──────────────────────────┬────────────────────────────────────────────────────────────┬────────────────────────────────────────────┐
│      Store      │        Backed By         │                          Used By                           │                  Contains                  │
├─────────────────┼──────────────────────────┼────────────────────────────────────────────────────────────┼────────────────────────────────────────────┤
│ EpisodicStore   │ SQLite (~/.xnch/xnch.db) │ xnch routes (memory/read, memory/write, execution/outcome) │ Decision episodes from the governance flow │
├─────────────────┼──────────────────────────┼────────────────────────────────────────────────────────────┼────────────────────────────────────────────┤
│ PgEpisodicStore │ agentmemory (ChromaDB)   │ consolidation job, context_assembler                       │ Episodes stored via store_episode()        │
└─────────────────┴──────────────────────────┴────────────────────────────────────────────────────────────┴────────────────────────────────────────────┘

The consolidation job reads from agentmemory. The decision flow writes to SQLite. They are different databases with different schemas and different episode IDs. The nightly consolidation job has nothing to consolidate from the actual decision flow, and context_assembler's semantic search returns nothing meaningful from the governance pipeline.

M2 — WorkingMemory exists but is not in xnch app state
working_memory.py is a complete Redis-backed conversation store with per-session turns, context keys, and TTL. It is never instantiated in xnch/xnch/main.py's lifespan. The xnch app state has kv_cache (also Redis, but for session dedup and rate limiting only). Multi-turn conversation history is never written or read. Every session starts cold with no prior exchange context.

M3 — xnch.db is not at the path mounted in K8s
xnch/xnch/config.py:Settings.db_path returns ~/.xnch/xnch.db (home directory). The K8s manifest mounts the PVC at /data. The env var XNCH_BASE_DIR is not set in the deployment manifest. So ~/.xnch/xnch.db lands inside the container's home directory — on the ephemeral container layer, not on the 20Gi PVC. Data survives restarts only by accident (pod not evicted), not by design.

M4 — PgEpisodicStore.store_decision_episode() raises RuntimeError unconditionally
The postgres-backed path (pg_episodic_store.py:183) checks if not self._pool: raise RuntimeError(...). connect() is a no-op (line 23: pass). The pool is never initialized. So store_decision_episode always raises. The agentmemory-based methods work, but any code path expecting the Postgres-native storage fails at runtime.

M5 — GraphStore is agentmemory-backed, not Kuzu
The gap report flags Kuzu as missing. The code uses agentmemory categories (entities, relations) as a graph store. query_entity_connections() does get_memories(RELATIONS_CATEGORY, n_results=5000) — a full scan every time with no index. At scale this is O(n) per entity lookup. Kuzu was the planned graph backend; agentmemory is a vector store being used as a graph store without proper graph traversal.

M6 — Sensory buffer exists but nothing writes to it
sensory_buffer.py is referenced in context_assembler.py:80 (await sensory_buffer.read_recent("voice", limit=3)). The perception daemonset image doesn't exist. No voice daemon or file watcher is running. The sensory buffer would return empty on every call.

M7 — pattern_store uses SQLite, but PgEpisodicStore uses agentmemory
Pattern extraction reads from EpisodicStore (SQLite) and writes to PatternStore (also SQLite). But the consolidation path tries to operate on agentmemory episodes. The learning loop's input (SQLite episodes) and the consolidation job's input (agentmemory episodes) are two separate populations. Patterns extracted from SQLite are never surfaced to context_assembler's semantic search (which reads from agentmemory).

---
Missing Components (Confirmed Absent)

┌────────────────────────────────────────────────┬────────────────────────────────┬─────────────────────────────────────────────────┐
│                   Component                    │             Status             │                     Impact                      │
├────────────────────────────────────────────────┼────────────────────────────────┼─────────────────────────────────────────────────┤
│ Execution runner service                       │ No code, no manifest, no image │ Every dispatch silently fails                   │
├────────────────────────────────────────────────┼────────────────────────────────┼─────────────────────────────────────────────────┤
│ /nexi/chat or equivalent public chat API       │ No route on any service        │ Cannot call from OpenClaw or Telegram           │
├────────────────────────────────────────────────┼────────────────────────────────┼─────────────────────────────────────────────────┤
│ XNCH_NEXI_BASE_URL in xnch K8s manifest        │ Env var missing                │ xnch cannot reach nexi                          │
├────────────────────────────────────────────────┼────────────────────────────────┼─────────────────────────────────────────────────┤
│ XNCH_BASE_DIR=/data in xnch K8s manifest       │ Env var missing                │ SQLite writes to ephemeral layer                │
├────────────────────────────────────────────────┼────────────────────────────────┼─────────────────────────────────────────────────┤
│ create_episode() call in verdict/session path  │ No caller                      │ Episodes never created, learning loop dead      │
├────────────────────────────────────────────────┼────────────────────────────────┼─────────────────────────────────────────────────┤
│ WorkingMemory in xnch app state                │ Never instantiated             │ No conversation turn history                    │
├────────────────────────────────────────────────┼────────────────────────────────┼─────────────────────────────────────────────────┤
│ Kuzu graph database                            │ Not installed, not called      │ Graph store falls back to agentmemory full-scan │
├────────────────────────────────────────────────┼────────────────────────────────┼─────────────────────────────────────────────────┤
│ Mem0 client in nexi/xnch code                  │ No import, no calls            │ mem0 pod is orphaned                            │
├────────────────────────────────────────────────┼────────────────────────────────┼─────────────────────────────────────────────────┤
│ Zep client in nexi/xnch code                   │ No import, no calls            │ zep pod is orphaned                             │
├────────────────────────────────────────────────┼────────────────────────────────┼─────────────────────────────────────────────────┤
│ Clarification re-entry (/session/{id}/clarify) │ Returns 501                    │ Clarification loop has no exit                  │
└────────────────────────────────────────────────┴────────────────────────────────┴─────────────────────────────────────────────────┘

---
Priority Fix Order

Fix now (blocks everything else):
1. Add XNCH_NEXI_BASE_URL=http://nexi:8000 to xnch K8s manifest — xnch can't reach nexi without this
2. Add XNCH_BASE_DIR=/data to xnch K8s manifest — SQLite data is ephemeral without this
3. Add create_episode() call in verdict.py before issuing the execution token — learning loop is dead without this
4. Fix run_early() → run() in memory.py:103
5. Add outcome_score_predicted to _fire_nexi_callback payload in execution.py

Fix next (architecture completeness):

6. Add NEXI_EXECUTION_RUNNER_URL to nexi manifest and build/stub an execution runner — or at minimum make dispatch log+succeed gracefully when no runner is available
7. Add a /chat or /v1/chat/completions route to xnch that wraps session_init in an OpenAI-compatible envelope — OpenClaw needs this
8. Implement POST /session/{session_id}/clarify — the clarification loop is a dead end
9. Wire WorkingMemory into xnch app state and call append_turn() after each session

Fix in Phase 1 (memory unification):

10. Decide on one canonical episodic store and migrate the other — either SQLite for v0 (simplest) or agentmemory for both decision episodes and free-form memory
11. Set connect() in PgEpisodicStore to actually initialize a pool, or remove the postgres-native methods that raise RuntimeError
12. Wire mem0 client for long-term memory retrieval in context_assembler, or wire agentmemory consistently as the single long-term store
13. Replace GraphStore.query_entity_connections() O(n) full scan with Kuzu or at minimum an indexed agentmemory filter
