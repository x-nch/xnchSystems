"""LangGraph checkpoint setup — run once to create tables."""
import os
from langgraph.checkpoint.postgres import PostgresSaver

DATABASE_URL = os.environ.get("XNCH_POSTGRES_URL", "postgresql://localhost:5432/xnch")

def setup():
    with PostgresSaver.from_conn_string(DATABASE_URL) as checkpointer:
        checkpointer.setup()
        print("PostgresSaver tables created successfully")

if __name__ == "__main__":
    setup()
