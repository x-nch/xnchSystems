"""Create Memgraph schema for XNCH/Nexi migration.

Includes indexes, constraints, and vector index for GraphRAG retrieval.
Per Memgraph GraphRAG skill: vector index on Chunk(embedding) for hybrid retrieval.
"""
import os
from neo4j import GraphDatabase

URI = os.environ.get("MEMGRAPH_URI", "bolt://localhost:7687")
USER = os.environ.get("MEMGRAPH_USERNAME", "")
PASS = os.environ.get("MEMGRAPH_PASSWORD", "")

SCHEMA_CYPHER = [
    # Entity nodes
    "CREATE INDEX ON :Entity(id)",
    "CREATE INDEX ON :Entity(name)",
    "CREATE INDEX ON :Entity(type)",
    "CREATE CONSTRAINT ON (e:Entity) REQUIRE e.id IS UNIQUE",
    # Episode nodes
    "CREATE INDEX ON :Episode(id)",
    "CREATE INDEX ON :Episode(intent_class)",
    "CREATE INDEX ON :Episode(action_type)",
    # Pattern nodes
    "CREATE INDEX ON :Pattern(id)",
    "CREATE INDEX ON :Pattern(context_signature)",
    # Document/Chunk for GraphRAG
    "CREATE INDEX ON :Document(id)",
    "CREATE INDEX ON :Chunk(id)",
    # Vector index for hybrid retrieval (GraphRAG skill step 4)
    # Dimension must match your embedding model (384 for all-MiniLM-L6-v2, 1536 for OpenAI)
    """CREATE VECTOR INDEX vs_chunks
    ON :Chunk(embedding)
    WITH CONFIG {"dimension": 384, "capacity": 100000, "metric": "cos"}""",
]


def create_schema():
    driver = GraphDatabase.driver(URI, auth=(USER, PASS))
    with driver.session() as session:
        for stmt in SCHEMA_CYPHER:
            try:
                session.run(stmt)
                print(f"OK: {stmt.strip()[:80]}")
            except Exception as e:
                print(f"SKIP: {stmt.strip()[:80]} ({e})")

        # Update query planner statistics after schema creation
        try:
            session.run("ANALYZE GRAPH")
            print("OK: ANALYZE GRAPH")
        except Exception as e:
            print(f"SKIP: ANALYZE GRAPH ({e})")

    driver.close()
    print("Schema setup complete")


if __name__ == "__main__":
    create_schema()
