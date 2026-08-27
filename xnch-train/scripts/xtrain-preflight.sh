#!/usr/bin/env bash
set -euo pipefail

# xtrain-preflight.sh — ExecStartPre gate for xtrain-cycle.service
#
# STUB (Task 3): performs no real checks yet. Real preflight logic
# (GPU memory availability, dataset/checkpoint readiness, Goal approval
# verification, lock-group sanity) lands in Task 6.
#
# Exits 0 so the cycle may proceed; replace with real checks in Task 6.

echo "[xtrain-preflight] STUB: preflight checks not yet implemented (Task 6)."
echo "[xtrain-preflight] reporting OK to allow cycle start."
exit 0
