"""Migrate entities from agentmemory to Memgraph."""
import os
from agentmemory import get_memories
from neo4j import GraphDatabase

URI = os.environ.get("MEMGRAPH_URI", "bolt://localhost:7687")
USER = os.environ.get("MEMGRAPH_USERNAME", "")
PASS = os.environ.get("MEMGRAPH_PASSWORD", "")


def migrate():
    driver = GraphDatabase.driver(URI, auth=(USER, PASS))
    entities = get_memories("entities", n_results=10000)
    print(f"Found {len(entities)} entities to migrate")

    migrated = 0
    with driver.session() as session:
        for entity in entities:
            meta = entity.get("metadata", {})
            entity_id = meta.get("entity_id", entity.get("id", ""))
            name = meta.get("name", entity.get("document", ""))
            type_ = meta.get("type", "UNKNOWN")

            if not entity_id or not name:
                continue

            session.run(
                """
                MERGE (e:Entity {id: $id})
                SET e.name = $name, e.type = $type, e.updated_at = datetime()
                """,
                id=entity_id, name=name, type=type_,
            )
            migrated += 1

    driver.close()
    print(f"Migrated {migrated} entities to Memgraph")


if __name__ == "__main__":
    migrate()
