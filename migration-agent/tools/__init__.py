"""Migration agent tools — Phase 0–3."""
from .infrastructure import (
    deploy_memgraph,
    setup_postgres_checkpointer,
    add_dependencies,
    verify_infrastructure,
)
from .graph_migration import (
    create_memgraph_schema,
    migrate_entities_to_memgraph,
    migrate_relations_to_memgraph,
    validate_graph_migration,
)
from .memory_migration import (
    create_composite_backend,
    migrate_episodic_to_store,
    migrate_patterns_to_store,
    validate_memory_migration,
)
from .pipeline_migration import (
    define_decision_state,
    create_langgraph_pipeline,
    add_human_in_the_loop,
    validate_pipeline_migration,
)

__all__ = [
    # Phase 0 — Infrastructure
    "deploy_memgraph",
    "setup_postgres_checkpointer",
    "add_dependencies",
    "verify_infrastructure",
    # Phase 1 — Graph Migration
    "create_memgraph_schema",
    "migrate_entities_to_memgraph",
    "migrate_relations_to_memgraph",
    "validate_graph_migration",
    # Phase 2 — Memory Migration
    "create_composite_backend",
    "migrate_episodic_to_store",
    "migrate_patterns_to_store",
    "validate_memory_migration",
    # Phase 3 — Pipeline Migration
    "define_decision_state",
    "create_langgraph_pipeline",
    "add_human_in_the_loop",
    "validate_pipeline_migration",
]
