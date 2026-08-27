#!/usr/bin/env bash
set -euo pipefail
# Incremental rebuild of the code-review-graph knowledge graph for this repo.
REPO="$(git rev-parse --show-toplevel 2>/dev/null || echo /Users/xnch/xnchSystems)"
exec uvx code-review-graph update --repo "$REPO"
