# Phase 2: Memory Migration to Deep Agents

## Tools
- `create_composite_backend` — Create CompositeBackend with routes for /episodes/, /patterns/
- `migrate_episodic_to_store` — Move episodes from SQLite to StoreBackend
- `migrate_patterns_to_store` — Move patterns from SQLite to StoreBackend
- `validate_memory_migration` — Compare old vs new counts

## Acceptance Criteria
- [ ] CompositeBackend configured with correct routes
- [ ] All episodes migrated to StoreBackend
- [ ] All patterns migrated to StoreBackend
- [ ] validate_memory_migration passes
- [ ] Old episodic_store.py marked deprecated

## Architecture
```
StateBackend (default)  ←  session state, working memory
    ↓
StoreBackend (/episodes/)  ←  episodic memories
StoreBackend (/patterns/)  ←  pattern records
StoreBackend (/entities/)  ←  entity snapshots
```
