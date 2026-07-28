"""Migrate relationships from agentmemory to Memgraph."""
import os
from agentmemory import get_memories
from neo4j import GraphDatabase

URI = os.environ.get("MEMGRAPH_URI", "bolt://localhost:7687")
USER = os.environ.get("MEMGRAPH_USERNAME", "")
PASS = os.environ.get("MEMGRAPH_PASSWORD", "")


def migrate():
    driver = GraphDatabase.driver(URI, auth=(USER, PASS))
    relations = get_memories("relations", n_results=10000)
    print(f"Found {len(relations)} relations to migrate")

    migrated = 0
    with driver.session() as session:
        for rel in relations:
            meta = rel.get("metadata", {})
            from_id = meta.get("from_id", "")
            to_id = meta.get("to_id", "")
            rel_type = meta.get("rel_type", "RELATES_TO")
            confidence = float(meta.get("confidence", 0.5))

            if not from_id or not to_id:
                continue

            session.run(
                """
                MATCH (a:Entity {id: $from_id})
                MATCH (b:Entity {id: $to_id})
                MERGE (a)-[r:RELATES_TO {type: $rel_type}]->(b)
                SET r.confidence = $confidence, r.updated_at = datetime()
                """,
                from_id=from_id, to_id=to_id,
                rel_type=rel_type, confidence=confidence,
            )
            migrated += 1

    driver.close()
    print(f"Migrated {migrated} relationships to Memgraph")


if __name__ == "__main__":
    migrate()
