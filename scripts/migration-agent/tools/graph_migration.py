"""Graph migration tools for Phase 1: Memgraph schema, entity/relation migration."""

import json
from pathlib import Path
from langchain.tools import tool

CODEBASE_ROOT = Path("/Users/xnch/xnchSystems")


@tool(parse_docstring=True)
def create_memgraph_schema(dry_run: bool = True) -> str:
    """Create Memgraph schema for the migration.

    Creates nodes: Entity, Episode, Pattern, Document, Chunk
    Creates relationships: MENTIONED_IN, RELATES_TO, LED_TO, APPLIES_TO, HAS_CHUNK
    Creates indexes on Entity.name, Episode.id, Pattern.context_signature

    Args:
        dry_run: If True, only output the Cypher without executing.
    """
    schema_cypher = """// Memgraph Schema for XNCH/Nexi

// Node labels and properties
CREATE INDEX ON :Entity(id);
CREATE INDEX ON :Entity(name);
CREATE INDEX ON :Entity(type);

CREATE INDEX ON :Episode(id);
CREATE INDEX ON :Episode(intent_class);
CREATE INDEX ON :Episode(action_type);

CREATE INDEX ON :Pattern(id);
CREATE INDEX ON :Pattern(context_signature);

CREATE INDEX ON :Document(id);
CREATE INDEX ON :Chunk(id);
CREATE INDEX ON :Chunk(embedding);

// Relationship types (no indexes needed, but document schema)
// (Entity)-[:MENTIONED_IN]->(Episode)
// (Entity)-[:RELATES_TO {confidence}]->(Entity)
// (Episode)-[:LED_TO {outcome, success_rate}]->(Pattern)
// (Pattern)-[:APPLIES_TO {confidence}]->(Entity)
// (Document)-[:HAS_CHUNK]->(Chunk)
// (Chunk)-[:NEXT]->(Chunk)
"""
    if dry_run:
        return f"Schema Cypher (dry run):\\n{schema_cypher}"

    script_path = CODEBASE_ROOT / "scripts" / "create_memgraph_schema.py"
    script_content = f'''"""Create Memgraph schema."""
import os
from langchain_memgraph.graphs.memgraph import Memgraph

graph = Memgraph(
    url=os.environ.get("MEMGRAPH_URI", "bolt://localhost:7687"),
    username=os.environ.get("MEMGRAPH_USERNAME", ""),
    password=os.environ.get("MEMGRAPH_PASSWORD", ""),
)

schema_cypher = """{schema_cypher}"""

for statement in schema_cypher.split(";"):
    statement = statement.strip()
    if statement and not statement.startswith("//"):
        graph.query(statement)

print("Memgraph schema created successfully")
'''
    script_path.write_text(script_content)
    return f"Schema script written to {script_path}. Run with: python {script_path}"


@tool(parse_docstring=True)
def migrate_entities_to_memgraph(dry_run: bool = True) -> str:
    """Migrate entities from agentmemory to Memgraph.

    Reads all entities from the 'entities' category in agentmemory
    and creates Entity nodes in Memgraph.

    Args:
        dry_run: If True, only output the migration plan without executing.
    """
    migration_code = '''"""Migrate entities from agentmemory to Memgraph."""
import os
import json
from agentmemory import get_memories
from langchain_memgraph.graphs.memgraph import Memgraph

graph = Memgraph(
    url=os.environ.get("MEMGRAPH_URI", "bolt://localhost:7687"),
    username=os.environ.get("MEMGRAPH_USERNAME", ""),
    password=os.environ.get("MEMGRAPH_PASSWORD", ""),
)

# Read all entities from agentmemory
entities = get_memories("entities", n_results=10000)
print(f"Found {len(entities)} entities to migrate")

migrated = 0
for entity in entities:
    meta = entity.get("metadata", {})
    entity_id = meta.get("entity_id", entity.get("id", ""))
    name = meta.get("name", entity.get("document", ""))
    type_ = meta.get("type", "UNKNOWN")

    if not entity_id or not name:
        continue

    # Upsert into Memgraph
    graph.query(
        """
        MERGE (e:Entity {id: $id})
        SET e.name = $name, e.type = $type, e.updated_at = datetime()
        """,
        params={"id": entity_id, "name": name, "type": type_},
    )
    migrated += 1

print(f"Migrated {migrated} entities to Memgraph")
'''
    script_path = CODEBASE_ROOT / "scripts" / "migrate_entities.py"

    if dry_run:
        return f"Migration script (dry run) would be written to {script_path}"

    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(migration_code)
    return f"Entity migration script written to {script_path}. Run with: python {script_path}"


@tool(parse_docstring=True)
def migrate_relations_to_memgraph(dry_run: bool = True) -> str:
    """Migrate relationships from agentmemory to Memgraph.

    Reads all relations from the 'relations' category in agentmemory
    and creates RELATES_TO edges in Memgraph.

    Args:
        dry_run: If True, only output the migration plan without executing.
    """
    migration_code = '''"""Migrate relationships from agentmemory to Memgraph."""
import os
from agentmemory import get_memories
from langchain_memgraph.graphs.memgraph import Memgraph

graph = Memgraph(
    url=os.environ.get("MEMGRAPH_URI", "bolt://localhost:7687"),
    username=os.environ.get("MEMGRAPH_USERNAME", ""),
    password=os.environ.get("MEMGRAPH_PASSWORD", ""),
)

# Read all relations from agentmemory
relations = get_memories("relations", n_results=10000)
print(f"Found {len(relations)} relations to migrate")

migrated = 0
for rel in relations:
    meta = rel.get("metadata", {})
    from_id = meta.get("from_id", "")
    to_id = meta.get("to_id", "")
    rel_type = meta.get("rel_type", "RELATES_TO")
    confidence = float(meta.get("confidence", 0.5))

    if not from_id or not to_id:
        continue

    # Create relationship in Memgraph
    graph.query(
        """
        MATCH (a:Entity {id: $from_id})
        MATCH (b:Entity {id: $to_id})
        MERGE (a)-[r:RELATES_TO {type: $rel_type}]->(b)
        SET r.confidence = $confidence, r.updated_at = datetime()
        """,
        params={"from_id": from_id, "to_id": to_id, "rel_type": rel_type, "confidence": confidence},
    )
    migrated += 1

print(f"Migrated {migrated} relationships to Memgraph")
'''
    script_path = CODEBASE_ROOT / "scripts" / "migrate_relations.py"

    if dry_run:
        return f"Migration script (dry run) would be written to {script_path}"

    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(migration_code)
    return f"Relation migration script written to {script_path}. Run with: python {script_path}"


@tool(parse_docstring=True)
def validate_graph_migration() -> str:
    """Validate graph migration by comparing agentmemory and Memgraph results.

    Runs identical queries against both stores and compares output.
    """
    validation_code = '''"""Validate graph migration — compare agentmemory vs Memgraph."""
import os
from agentmemory import get_memories, search_memory
from langchain_memgraph.graphs.memgraph import Memgraph

graph = Memgraph(
    url=os.environ.get("MEMGRAPH_URI", "bolt://localhost:7687"),
    username=os.environ.get("MEMGRAPH_USERNAME", ""),
    password=os.environ.get("MEMGRAPH_PASSWORD", ""),
)

def compare_entity_counts():
    am_entities = get_memories("entities", n_results=10000)
    result = graph.query("MATCH (e:Entity) RETURN count(e) as count")
    mg_count = result[0]["count"] if result else 0
    return len(am_entities), mg_count

def compare_relation_counts():
    am_relations = get_memories("relations", n_results=10000)
    result = graph.query("MATCH ()-[r:RELATES_TO]->() RETURN count(r) as count")
    mg_count = result[0]["count"] if result else 0
    return len(am_relations), mg_count

def compare_entity_connections(entity_id):
    from xnch.memory.graph_store import GraphStore
    gs = GraphStore()
    am_connections = gs.query_entity_connections(entity_id)

    result = graph.query(
        """
        MATCH (e:Entity {id: $id})-[r:RELATES_TO]-(other:Entity)
        RETURN other.id as connected_id, other.name as connected_name,
               type(r) as rel_type, r.confidence as confidence
        """,
        params={"id": entity_id},
    )
    mg_connections = [dict(r) for r in result]
    return am_connections, mg_connections

# Run validation
am_entities, mg_entities = compare_entity_counts()
am_relations, mg_relations = compare_relation_counts()

print(f"Entities: agentmemory={am_entities}, memgraph={mg_entities}")
print(f"Relations: agentmemory={am_relations}, memgraph={mg_relations}")

if am_entities == mg_entities and am_relations == mg_relations:
    print("VALIDATION PASSED: Counts match")
else:
    print("VALIDATION FAILED: Counts mismatch")
'''
    script_path = CODEBASE_ROOT / "scripts" / "validate_graph.py"
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(validation_code)
    return f"Validation script written to {script_path}. Run with: python {script_path}"
