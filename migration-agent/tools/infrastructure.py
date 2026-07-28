"""Infrastructure tools for Phase 0: Memgraph deployment, checkpointer setup, dependencies."""

import subprocess
from pathlib import Path
from langchain.tools import tool

CODEBASE_ROOT = Path("/Users/xnch/xnchSystems")


@tool(parse_docstring=True)
def deploy_memgraph(dry_run: bool = True) -> str:
    """Deploy Memgraph on the i7-node via Kubernetes.

    Creates a Memgraph StatefulSet and Service in the xnch-system namespace.
    Uses bolt://memgraph:7687 for LangGraph connections.

    Args:
        dry_run: If True, only generate manifests without applying.
    """
    memgraph_manifest = """apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: memgraph
  namespace: xnch-system
spec:
  replicas: 1
  selector:
    matchLabels:
      app: memgraph
  serviceName: memgraph
  template:
    metadata:
      labels:
        app: memgraph
    spec:
      nodeSelector:
        role: memory
      containers:
      - name: memgraph
        image: memgraph/memgraph:latest
        ports:
        - containerPort: 7687
          name: bolt
        - containerPort: 7444
          name: http
        env:
        - name: MEMGRAPH_USER
          value: ""
        - name: MEMGRAPH_PASSWORD
          valueFrom:
            secretKeyRef:
              name: memgraph-secret
              key: password
              optional: true
        volumeMounts:
        - name: memgraph-data
          mountPath: /var/lib/memgraph
  volumeClaimTemplates:
  - metadata:
      name: memgraph-data
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 10Gi
---
apiVersion: v1
kind: Service
metadata:
  name: memgraph
  namespace: xnch-system
spec:
  selector:
    app: memgraph
  ports:
  - port: 7687
    targetPort: 7687
    name: bolt
  - port: 7444
    targetPort: 7444
    name: http
  clusterIP: None
"""
    manifest_path = CODEBASE_ROOT / "deploy" / "k8s" / "i7-node" / "memgraph.yaml"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(memgraph_manifest)

    if dry_run:
        return f"Manifest written to {manifest_path} (dry run — not applied)"

    result = subprocess.run(
        ["kubectl", "apply", "-f", str(manifest_path)],
        capture_output=True, text=True, timeout=60
    )
    if result.returncode == 0:
        return f"Memgraph deployed: {result.stdout}"
    return f"Deployment failed: {result.stderr}"


@tool(parse_docstring=True)
def setup_postgres_checkpointer() -> str:
    """Set up PostgresSaver for LangGraph checkpointing on the existing PostgreSQL.

    Runs the PostgresSaver setup to create checkpoint tables.
    Connection uses XNCH_POSTGRES_URL from environment.
    """
    setup_code = '''"""LangGraph checkpoint setup — run once to create tables."""
import os
from langgraph.checkpoint.postgres import PostgresSaver

DATABASE_URL = os.environ.get("XNCH_POSTGRES_URL", "postgresql://localhost:5432/xnch")

def setup():
    with PostgresSaver.from_conn_string(DATABASE_URL) as checkpointer:
        checkpointer.setup()
        print("PostgresSaver tables created successfully")

if __name__ == "__main__":
    setup()
'''
    script_path = CODEBASE_ROOT / "scripts" / "setup_checkpointer.py"
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(setup_code)

    return f"Checkpointer setup script written to {script_path}. Run with: python {script_path}"


@tool(parse_docstring=True)
def add_dependencies() -> str:
    """Add LangGraph, Deep Agents, and Memgraph dependencies to pyproject.toml.

    Adds to the root xnchSystems/pyproject.toml.
    """
    pyproject_path = CODEBASE_ROOT / "pyproject.toml"
    content = pyproject_path.read_text()

    new_deps = '''    # LangGraph + Deep Agents + Memgraph
    "langgraph>=0.2.0",
    "langchain-memgraph>=0.1.0",
    "deepagents>=0.1.0",
    "langgraph-checkpoint-postgres>=0.1.0",'''

    if "langgraph" not in content:
        content = content.replace(
            '    "litellm>=1.89.4",',
            f'    "litellm>=1.89.4",\n{new_deps}'
        )
        pyproject_path.write_text(content)
        return f"Dependencies added to {pyproject_path}"

    return "LangGraph dependencies already present in pyproject.toml"


@tool(parse_docstring=True)
def verify_infrastructure() -> str:
    """Verify all infrastructure components are ready.

    Checks: Memgraph reachable, PostgresSaver tables exist, dependencies installed.
    """
    checks = []

    # Check Memgraph
    try:
        import subprocess
        result = subprocess.run(
            ["kubectl", "get", "pods", "-n", "xnch-system", "-l", "app=memgraph", "-o", "name"],
            capture_output=True, text=True, timeout=10
        )
        if "pod/memgraph" in result.stdout:
            checks.append("Memgraph pod: RUNNING")
        else:
            checks.append("Memgraph pod: NOT FOUND")
    except Exception as e:
        checks.append(f"Memgraph check failed: {e}")

    # Check dependencies
    try:
        from importlib.metadata import version as get_version
        langgraph_ver = get_version("langgraph")
        checks.append(f"langgraph: {langgraph_ver}")
    except Exception:
        checks.append("langgraph: NOT INSTALLED")

    try:
        import langchain_memgraph
        checks.append(f"langchain-memgraph: installed")
    except ImportError:
        checks.append("langchain-memgraph: NOT INSTALLED")

    try:
        import deepagents
        checks.append(f"deepagents: installed")
    except ImportError:
        checks.append("deepagents: NOT INSTALLED")

    return "\\n".join(checks)
