#!/usr/bin/env bash
set -euo pipefail

# xtrain-restart-vllm.sh — ExecStartPost for xtrain-cycle.service
#
# STUB (Task 3): performs no real vLLM restart yet. Real logic
# (re-enabling/restoring vLLM-ornith serving after a Train Window, and
# confirming the Conflicts lock group released) lands in Task 6.
#
# Exits 0; replace with real restart/smoke logic in Task 6.

echo "[xtrain-restart-vllm] STUB: vLLM restart not yet implemented (Task 6)."
echo "[xtrain-restart-vllm] reporting OK to allow cycle completion."
exit 0
