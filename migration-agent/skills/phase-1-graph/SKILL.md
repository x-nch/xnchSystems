# Phase 1: Graph Migration to Memgraph

## Tools
- `create_memgraph_schema` — Create node labels, relationships, indexes
- `migrate_entities_to_memgraph` — Pull from graph_store.py, write to Memgraph
- `migrate_relations_to_memgraph` — Pull relationships, write to Memgraph
- `validate_graph_migration` — Compare old vs new entity/relation counts

## Acceptance Criteria
- [ ] Memgraph schema created with all node labels and relationship types
- [ ] All entities migrated with correct properties
- [ ] All relationships migrated
- [ ] validate_graph_migration passes

## Cypher Setup
```cypher
CREATE INDEX ON :Entity(id);
CREATE INDEX ON :Entity(class);
CREATE INDEX ON :Actor(id);
CREATE INDEX ON :Actor(role);
CREATE CONSTRAINT ON (e:Entity) REQUIRE e.id IS UNIQUE;
```
