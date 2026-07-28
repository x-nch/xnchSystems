"""Validate graph migration — compare agentmemory vs Memgraph."""
import os
from agentmemory import get_memories
from neo4j import GraphDatabase

URI = os.environ.get("MEMGRAPH_URI", "bolt://localhost:7687")
USER = os.environ.get("MEMGRAPH_USERNAME", "")
PASS = os.environ.get("MEMGRAPH_PASSWORD", "")


def validate():
    driver = GraphDatabase.driver(URI, auth=(USER, PASS))

    am_entities = get_memories("entities", n_results=10000)
    am_relations = get_memories("relations", n_results=10000)

    with driver.session() as session:
        mg_entities = session.run("MATCH (e:Entity) RETURN count(e) AS count").single()["count"]
        mg_relations = session.run("MATCH ()-[r:RELATES_TO]->() RETURN count(r) AS count").single()["count"]

    driver.close()

    print(f"Entities: agentmemory={len(am_entities)}, memgraph={mg_entities}")
    print(f"Relations: agentmemory={len(am_relations)}, memgraph={mg_relations}")

    if len(am_entities) == mg_entities and len(am_relations) == mg_relations:
        print("VALIDATION PASSED: Counts match")
    else:
        print("VALIDATION FAILED: Counts mismatch")


if __name__ == "__main__":
    validate()
