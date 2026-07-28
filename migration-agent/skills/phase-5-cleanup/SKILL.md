# Phase 5: Cleanup & Documentation

## Steps
1. Remove deprecated files (old pipeline, graph_store, episodic_store)
2. Update imports across xnch codebase
3. Update MIGRATION_PLAN.md with completion status
4. Remove migration-agent tools for deprecated code
5. Archive old pipeline as backup

## Acceptance Criteria
- [ ] No imports reference removed files
- [ ] All tests pass
- [ ] MIGRATION_PLAN.md updated
- [ ] Old code archived in git tag

## Files to Remove
- `xnch/memory/graph_store.py` (replaced by Memgraph)
- `xnch/memory/episodic_store.py` (replaced by StoreBackend)
- `xnch/memory/pattern_store.py` (replaced by StoreBackend)
- `nexi/pipeline/sequential_decision_engine.py` (replaced by pipeline_graph.py)
