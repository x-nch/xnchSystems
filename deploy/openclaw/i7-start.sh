#!/bin/bash
set -euo pipefail

echo "[nexi] Checking XNCH gateway health..."
curl -sf http://localhost:30800/health || { echo '[nexi] FATAL: XNCH not ready'; exit 1; }

echo "[nexi] Fetching system prompt..."
NEXI_SYSTEM_PROMPT=$(curl -s http://localhost:30800/nexi/system-prompt)
export NEXI_SYSTEM_PROMPT

echo "[nexi] Surfacing proactive observations..."
PENDING=$(curl -s http://localhost:30800/nexi/memory/surface)
if [ "$PENDING" != '[]' ]; then
  echo '=== Nexi Observations ==='
  echo "$PENDING" | python3 -c 'import sys,json; [print(e["message"]) for e in json.load(sys.stdin)]'
  echo '========================='
fi

echo "[nexi] Launching OpenClaw..."
export PATH="/home/x-nch/.npm-global/bin:$PATH"
exec openclaw gateway run "$@"
