#!/usr/bin/env bash
# Loads all WorkflowCreateRequest JSON files into a running xnch control plane.
#
# Contract (see xnch/models/workflow.py + xnch/routes/workflows.py):
#   POST /workflows  (gated by X-Gateway-Token or X-Service-Key; or set
#                     XNCH_ALLOW_OPEN_GATEWAY=1 on the server for dev)
#
# GOTCHA 1: scheduled workflows need a cron string or they're manual-only.
#           All schedule-kind files here already include one.
# GOTCHA 2: execution is a PULL loop. Creating a workflow does NOT run it.
#           - manual workflows: something must POST /workflows/{id}/run
#           - schedule workflows: APScheduler fires /run on cron
#           - a workflow_executor_loop must poll POST /workflows/steps/claim
#             or APPROVED steps sit forever.
#
# Usage:
#   XNCH_GATEWAY_SECRET=xxx ./load_workflows.sh            # real gateway
#   ./load_workflows.sh                                     # open dev gateway
set -euo pipefail

BASE_URL="${XNCH_BASE_URL:-http://localhost:8000}"
SECRET="${XNCH_GATEWAY_SECRET:-}"
DIR="$(cd "$(dirname "$0")" && pwd)"

if [[ -n "$SECRET" ]]; then
  AUTH_HEADER=(-H "X-Gateway-Token: $SECRET")
else
  AUTH_HEADER=()
fi

shopt -s nullglob
FILES=("$DIR"/*.json)
[[ ${#FILES[@]} -eq 0 ]] && { echo "no workflow JSON found in $DIR"; exit 1; }

for f in "${FILES[@]}"; do
  name="$(basename "$f")"
  echo "==> loading $name"
  curl -fsS -X POST "$BASE_URL/workflows" \
    "${AUTH_HEADER[@]}" \
    -H "Content-Type: application/json" \
    --data-binary "@$f" \
    -o /tmp/wf_resp.json \
    && jq -r '.id + "  " + (.name // "?")' /tmp/wf_resp.json \
    || { echo "FAILED: $name"; cat /tmp/wf_resp.json; }
done
