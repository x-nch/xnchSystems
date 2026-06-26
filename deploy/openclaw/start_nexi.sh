#!/bin/bash
set -euo pipefail

echo "[nexi] Checking LiteLLM gateway health..."
curl -sf http://i7-node:4000/health || { echo '[nexi] FATAL: LiteLLM not ready'; exit 1; }

echo "[nexi] Fetching system prompt..."
NEXI_SYSTEM_PROMPT=$(curl -s http://i7-node:8000/nexi/system-prompt)
export NEXI_SYSTEM_PROMPT

echo "[nexi] Surfacing proactive observations..."
PENDING=$(curl -s http://i7-node:8000/nexi/memory/surface)
if [ "$PENDING" != '[]' ]; then
  echo '=== Nexi Observations ==='
  echo "$PENDING" | python3 -c 'import sys,json; [print(e["message"]) for e in json.load(sys.stdin)]'
  echo '========================='
fi

echo "[nexi] Launching OpenClaw..."
exec openclaw --config ~/.openclaw/config.yaml "$@"
