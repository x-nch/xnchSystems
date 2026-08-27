#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${REPO_ROOT:-$HOME/xnchSystems}"
MCP_DIR="$REPO_ROOT/mcp/superpowers-mcp"
[[ -d "$MCP_DIR" ]] || { echo "FAIL: $MCP_DIR missing (init submodules?)" >&2; exit 1; }
command -v node >/dev/null || { echo "FAIL: node not installed" >&2; exit 1; }
cd "$MCP_DIR"
echo "=== superpowers-mcp: npm install ==="
npm install --no-audit --no-fund
echo "=== superpowers-mcp: build ==="
npm run build
[[ -f build/index.js ]] || { echo "FAIL: build/index.js not produced" >&2; exit 1; }
echo "OK  superpowers-mcp built at $MCP_DIR/build/index.js"
