# Migration Plan: XNCH/Nexi → LangGraph + Deep Agents + Memgraph

## Executive Summary

Migrate the hand-rolled pipeline, memory, and graph systems in XNCH/Nexi to:
- **LangGraph** — Replace the sequential pipeline in `nexi/pipeline/` with a stateful graph
- **Deep Agents** — Replace ad-hoc memory backends with CompositeBackend (State + Store)
- **Memgraph** — Replace `agentmemory`-based graph store with a real graph database

---

## Current Architecture (What Exists)

### Nexi Pipeline (`nexi/nexi/pipeline/`)
Sequential steps, no graph, no checkpointing, no human-in-the-loop:
```
intent_interpreter → context_assembler → option_generator → policy_filter → evaluator → selector → plan_compiler → dispatch
```

### XNCH Memory (`xnch/xnch/memory/`)
Fragmented across 8+ stores:
- `sensory_buffer.py` — Redis L0
- `working_memory.py` — Redis L1
- `episodic_store.py` — SQLite
- `pg_episodic_store.py` — PostgreSQL + pgvector
- `graph_store.py` — agentmemory (ChromaDB wrapper)
- `relationship_store.py` — PostgreSQL
- `pattern_store.py` — SQLite
- `kv_cache.py` — Redis

### XNCH Graph (`xnch/xnch/memory/graph_store.py`)
- Uses `agentmemory` library (ChromaDB) for entity/relation storage
- No real graph traversal — just metadata filtering
- `query_entity_connections` loads ALL relations then filters in Python

### Policy Engine (`xnch/xnch/policy/engine.py`)
- YAML-based rules, first-match-wins
- Stateless evaluation, no graph awareness

---

## Target Architecture

### 1. LangGraph Decision Pipeline

Replace `nexi/nexi/pipeline/` with a LangGraph `StateGraph`:

```python
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres import PostgresSaver

class DecisionState(TypedDict):
    raw_input: str
    session_id: str
    trace_id: str
    intent: Intent
    context: AssembledContext
    options: list[PlanOption]
    policy_verdicts: list[PolicyDryRunResponse]
    evaluated: list[EvaluatedOption]
    selected: PlanOption | None
    compiled_plan: CompiledPlan | None

graph = StateGraph(DecisionState)

# Nodes (map from existing pipeline steps)
graph.add_node("classify_intent", classify_intent_node)
graph.add_node("assemble_context", assemble_context_node)
graph.add_node("generate_options", generate_options_node)
graph.add_node("filter_policy", filter_policy_node)
graph.add_node("evaluate", evaluate_node)
graph.add_node("select", select_node)
graph.add_node("compile_plan", compile_plan_node)
graph.add_node("dispatch", dispatch_node)

# Edges (with conditional routing)
graph.add_edge(START, "classify_intent")
graph.add_conditional_edges("classify_intent", route_by_intent_class)
graph.add_edge("assemble_context", "generate_options")
graph.add_edge("generate_options", "filter_policy")
graph.add_conditional_edges("filter_policy", route_by_verdict)  # BLOCK → END
graph.add_edge("evaluate", "select")
graph.add_conditional_edges("select", route_by_selection)  # CLARIFY → interrupt
graph.add_edge("compile_plan", "dispatch")
graph.add_edge("dispatch", END)

# Checkpointing for human-in-the-loop
checkpointer = PostgresSaver(conn)
compiled = graph.compile(checkpointer=checkpointer)
```

**Benefits:**
- Built-in checkpointing (resume after crashes)
- Human-in-the-loop at any node (e.g., policy DEFER → interrupt for human approval)
- State persistence across sessions
- Visual graph in LangSmith

### 2. Deep Agents Memory Layer

Replace `xnch/xnch/memory/` with CompositeBackend:

```python
from deepagents.backends import CompositeBackend, StateBackend, StoreBackend

def create_memory_backend(runtime):
    return CompositeBackend(
        default=StateBackend(runtime),           # Ephemeral working files
        routes={
            "/episodes/": StoreBackend(runtime),  # Persistent episodic memory
            "/patterns/": StoreBackend(runtime),  # Persistent pattern store
            "/entities/": StoreBackend(runtime),  # Persistent entity memory
        }
    )

# Production: use PostgresStore instead of InMemoryStore
from langgraph.store.postgres import PostgresStore

store = PostgresStore(connection_string="postgresql://...")
agent = create_deep_agent(backend=create_memory_backend, store=store)
```

**Migration mapping:**

| Current | Target | Why |
|---------|--------|-----|
| `sensory_buffer.py` (Redis) | StateBackend (thread-scoped) | Transient by nature |
| `working_memory.py` (Redis) | StateBackend (thread-scoped) | Session-scoped |
| `episodic_store.py` (SQLite) | StoreBackend `/episodes/` | Cross-session persistence |
| `pg_episodic_store.py` (PG) | StoreBackend `/episodes/` | Consolidate to one store |
| `graph_store.py` (agentmemory) | Memgraph (see below) | Real graph queries |
| `relationship_store.py` (PG) | Memgraph relationships | Native graph traversal |
| `pattern_store.py` (SQLite) | StoreBackend `/patterns/` | Cross-session persistence |
| `kv_cache.py` (Redis) | StateBackend or Redis | Keep Redis for hot cache |

### 3. Memgraph Graph Store

Replace `xnch/xnch/memory/graph_store.py` and `relationship_store.py`:

```python
from langchain_memgraph.graphs.memgraph import Memgraph
from langchain_memgraph import MemgraphToolkit

# Connection
graph = Memgraph(
    url="bolt://localhost:7687",
    username="",
    password="",
    refresh_schema=False,
)

# Schema (matches memgraph-graph-rag skill)
# Nodes: Entity {id, name, type, description}
#         Episode {id, intent_class, action_type, outcome}
#         Pattern {id, context_signature, success_rate}
# Relationships: (Entity)-[:MENTIONED_IN]->(Episode)
#                (Entity)-[:RELATES_TO]->(Entity)
#                (Episode)-[:LED_TO]->(Pattern)
#                (Pattern)-[:APPLIES_TO]->(Entity)

# Toolkit for agent tools
toolkit = MemgraphToolkit(graph=graph, llm=llm)
```

**Cypher queries replace Python filtering:**

```cypher
-- Current: load ALL relations, filter in Python
-- New: graph-native traversal
MATCH (e:Entity {id: $entity_id})-[r:RELATES_TO]-(other:Entity)
RETURN other.name, other.type, type(r), r.confidence
LIMIT 20

-- Impact radius (replaces get_impact_radius)
MATCH path = (target)-[:DEPENDS_ON|CALLS|IMPORTS*1..3]->(affected)
WHERE target.id = $entity_id
RETURN path

-- Pattern matching (replaces pattern_store fetch)
MATCH (p:Pattern)-[:APPLIES_TO]->(e:Entity)
WHERE e.type = $entity_class
  AND p.context_signature = $signature
RETURN p.success_rate, p.confidence
ORDER BY p.confidence DESC
LIMIT 5
```

---

## Migration Phases

### Phase 0: Infrastructure (Week 1) — DONE
- [x] Deploy Memgraph on i7-node (Docker/K8s)
- [x] Add Memgraph to `deploy/k8s/i7-node/memgraph.yaml`
- [x] Create `langchain-memgraph` + `memgraph` Python deps
- [x] Set up LangGraph checkpointer (PostgresSaver on existing PG) — `scripts/setup_checkpointer.py`
- [x] Add `langgraph`, `deepagents`, `langchain-memgraph` to pyproject.toml
- [x] Create `deploy/docker-compose.memgraph.yml` for local dev

### Phase 1: Graph Migration (Week 2) — DONE
- [x] Create Memgraph schema — `scripts/create_memgraph_schema.py`
- [x] Write migration scripts: agentmemory → Memgraph — `scripts/migrate_entities.py`, `scripts/migrate_relations.py`
- [x] Replace `graph_store.py` with Memgraph client — `xnch/xnch/memory/graph_store_memgraph.py`
- [x] Replace `relationship_store.py` queries with Cypher (native traversal in MemgraphGraphStore)
- [x] Validation script — `scripts/validate_graph.py`
- [ ] Test: all existing graph queries return same results (requires running Memgraph)

### Phase 2: Memory Consolidation (Week 3) — DONE
- [x] Set up Deep Agents CompositeBackend — `xnch/xnch/memory/composite_backend.py`
- [x] Migration scripts for episodic/pattern stores — `scripts/migrate_episodes.py` (via migration-agent)
- [x] Keep Redis for `sensory_buffer` and `kv_cache` (hot path) — unchanged
- [x] Validation script — `scripts/validate_memory.py`
- [ ] Remove `agentmemory` dependency (after all stores migrated)
- [ ] Test: episodic queries, pattern extraction still work (requires running PG)

### Phase 3: Pipeline → LangGraph (Week 4-5) — DONE
- [x] Define `DecisionState` TypedDict — `xnch/xnch/agents/decision_state.py`
- [x] Convert each pipeline step to a LangGraph node — `xnch/xnch/agents/pipeline_graph.py`
- [x] Add conditional edges (intent class routing, policy BLOCK)
- [x] Wire up PostgresSaver checkpointer (via `create_pipeline(checkpointer=...)`)
- [x] Add human-in-the-loop interrupts for EXECUTION actions — `pipeline_graph.py:select()`
- [x] HITL documentation — `docs/human-in-the-loop.md`
- [x] Pipeline validation script — `scripts/validate_pipeline.py`
- [ ] Migrate session management to LangGraph threads (requires runtime integration)
- [ ] Test: full decision cycle produces identical outcomes (requires running services)

### Phase 4: Agent Tools (Week 6) — PENDING
- [ ] Expose Memgraph as agent tools (run_query, retrieve_context)
- [ ] Expose Deep Agents memory as tools (read_file, write_file)
- [ ] Wire up LangGraph's MCP endpoint for external access
- [ ] Update AGENTS.md with new tool contracts

### Phase 5: Cleanup (Week 7) — PENDING
- [ ] Remove dead code: `episodic_store.py`, `graph_store.py`, `relationship_store.py`
- [ ] Remove `agentmemory` from dependencies
- [ ] Update K8s manifests (add Memgraph, update env vars)
- [ ] Update documentation
- [ ] Performance benchmarks: latency before/after

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Memgraph data loss during migration | Run agentmemory + Memgraph in parallel, validate with shadow reads |
| LangGraph pipeline regressions | Keep old pipeline as fallback, A/B test with session flag |
| Deep Agents state loss | Use PostgresStore (not InMemoryStore) for production |
| Performance regression | Benchmark Cypher queries vs Python filtering before migration |
| K8s deployment complexity | Phase infrastructure first, test locally before cluster deploy |

---

## Dependencies to Add

```toml
[project]
dependencies = [
    # Existing
    "agentmemory>=0.4.8",     # REMOVE after Phase 2
    "asyncpg>=0.31.0",
    "httpx>=0.28.1",
    "litellm>=1.89.4",
    # New
    "langgraph>=0.2.0",
    "langchain-memgraph>=0.1.0",
    "memgraph>=1.0.0",        # or use Bolt protocol directly
    "deepagents>=0.1.0",
    "langgraph-checkpoint-postgres>=0.1.0",
]
```

---

## What Stays the Same

- **FastAPI services** — XNCH and Nexi remain FastAPI, just with LangGraph underneath
- **Kubernetes topology** — i7-memory, i9-inference stays
- **PostgreSQL + pgvector** — Still used for LangGraph checkpointer and Deep Agents StoreBackend
- **Redis** — Still used for hot cache (sensory buffer, KV cache)
- **Policy YAML files** — Same format, same loader, just evaluated inside LangGraph nodes
- **Audit system** — EventLog and DecisionLedger unchanged
- **Auth system** — RSA keys, token signing unchanged
- **Perception daemonset** — Voice, vision, file watching unchanged
