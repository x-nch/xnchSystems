# Phase 0: Infrastructure Setup

## Tools
- `deploy_memgraph` — Start Memgraph via Docker
- `setup_postgres_checkpointer` — Create LangGraph checkpointers in PostgreSQL
- `add_dependencies` — Add langgraph, deep-agents, memgraph, langgraph-store-postgres to pyproject.toml
- `verify_infrastructure` — Check all services are running

## Acceptance Criteria
- [ ] Memgraph running on localhost:7687
- [ ] PostgreSQL checkpointers created (langgraph_agent_checkpoints, langgraph_agent_store)
- [ ] Dependencies installed in pyproject.toml
- [ ] verify_infrastructure returns all green

## Commands
```bash
docker compose -f deploy/docker-compose.memgraph.yml up -d
docker compose -f deploy/docker-compose.postgres.yml up -d
uv add langgraph langgraph-checkpoint-postgres langgraph-store-postgres deep-agents pymemgraph
```
