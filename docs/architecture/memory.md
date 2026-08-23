# Memory Architecture

Audience: devs/ops. Sources: `xnch/memory/*.py`,
[diagram suite §5](../architecture-suite.md), [memory-routing guide](../guides/memory-routing.md)
(kept for operational detail), consolidation job in `xnch/jobs/`.

Four automatic tiers plus one curated parallel store. Reads are fail-open:
a disconnected store yields an empty tier, never a request failure.

## Tiers

| Tier | Store | Backing | Shape & caps |
|---|---|---|---|
| **L0 Sensory** | `sensory_buffer.py` | Redis, TTL ≈60 s | raw perceptions (voice/screen/file); promoted on activity |
| **L1 Working** | `working_memory.py` | Redis | session turns, 20 sessions × 20 turns window |
| **L2 Episodic** | `pg_episodic_store.py` | Postgres + pgvector (MiniLM 384-d) | episodes; cap 200 within 30-day window; importance/decay/recall_count |
| **L3a Semantic graph** | `graph_store.py` | Kuzu file `~/.xnch/graph.kuzu` | entities + typed relations (written by consolidation) |
| **L3b Relations mirror** | `relationship_store.py` | Postgres `relationship_memory` | entity pairs, strength, reinforcement counts |

Parallel curated store: **agentmemory** service on :3111 (lessons, actions,
facts). It is *not* synced with the tiers — reachable only via explicit `am_*`
MCP tools in the chat loop. Routing between episodic recall and agentmemory is
policy-driven (`~/.xnch/memory-routing.yaml`, template
`infra/no-k3s/shared/memory-routing.example.yaml`; prefetch toggle
`XNCH_AM_PREFETCH_ENABLED`). See [memory-routing deploy runbook](../runbooks/memory-routing-deploy.md).

Governance-side stores (separate from the tiers): SQLite episodic mirror of the
verdict path (`~/.xnch/data/episodic.db`), pattern store (SQLite), quarantine
store (PG), goal store (SQLite), workflow/approval store. Schema: [data model](data-model.md).

## Unified tier graph (`tier_graph.py`)

Flattens L0–L3 into one node/edge model tagged by tier for muse's graph explorer:

- `GET /memory/graph/tiers` — per-tier counts + cross-tier edge count.
- `GET /memory/graph/all?tier=&search=&limit=&offset=` — paginated unified view.
- Live updates: `GET /memory/graph/stream` (SSE, via `graph_broadcaster.py`).

Node id prefixes avoid collisions: `sensory:` `working:` `episode:` `semantic:`.
Cross-tier edges: session ──`produced`──▶ episode (via `episodes.session_id`;
NULL for pre-migration rows), episode ──`mentions`──▶ entity (heuristic name
match in `raw_text`, ≤8 edges/episode).

## Writes — who writes what

| Source | Path | Lands in |
|---|---|---|
| Chat turn | `/nexi/chat` after guard `validate_memory_write` | L1 append + L2 episode (type=conversation) |
| Verdict | `POST /verdict` (policy engine authoritative) | DecisionLedger + SQLite episode PENDING + PG decision episode |
| Execution outcome | `POST /execution/outcome` | completes episode; nexi callback writes prediction_delta update |
| Identity facts | `POST /admin/reseed-identity` cold-start seeder | L2 identity episodes |
| Consolidation | daily timer → `POST /admin/consolidate` | L3a triples + L3b upserts + decay/archive |

## Consolidation & learning loops

**Consolidation (daily, systemd timer):**
fetch recent episodes → `graph_extractor` (LiteLLM `ornith`; opt-in local
llama.cpp via `XNCH_GRAPH_EXTRACTOR_MODEL=llama_cpp/<file>`) → triple
extraction → Kuzu + relationship upserts → decay scoring + archive below
threshold 0.1.

**Learning (6 h cron inside xnch):** `PatternExtractor` mines decision tuples
into `patterns` (min observations: `XNCH_PATTERN_MIN_OBSERVATIONS`=10) →
`ScoreAdapter` adjusts weights when accuracy ≥
`XNCH_SCORE_ADAPTER_ACCURACY_THRESHOLD`=0.6 → `PolicyCandidateGenerator`
proposes YAML policy candidates surfaced at
`GET /governance/policy-candidates`.

## Recall flow (read side)

Chat assembly order: L1 working turns (last 20) → L2 semantic recall
(`retrieve_similar`, top_k=5, min score `XNCH_MEMORY_RECALL_MIN_SCORE`=0.35)
→ L3 entity connections for mentioned names → sensory read_recent for voice
context → bump_recall on used episodes → system prompt build. Direct API:
`POST /nexi/memory/recall`. Manifest-based context for the decision path:
`POST /memory/read`.
