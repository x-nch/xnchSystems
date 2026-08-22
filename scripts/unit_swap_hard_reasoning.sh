#!/usr/bin/env bash
# Hard-reasoning operational mode: swap qwen-vl → ornith, then optionally reverse.
# Respects qwen-vl.service Conflicts=vllm-ornith.service (single-resident GPU).
set -euo pipefail

ACTION="${1:-to-ornith}"

case "$ACTION" in
  to-ornith)
    echo "Stopping qwen-vl; starting vllm-ornith (hard-reasoning window)..."
    sudo systemctl stop qwen-vl.service || true
    sudo systemctl start vllm-ornith.service
    sudo systemctl --no-pager --full status vllm-ornith.service | head -20
    ;;
  to-qwen)
    echo "Stopping vllm-ornith; starting qwen-vl (default resident)..."
    sudo systemctl stop vllm-ornith.service || true
    sudo systemctl start qwen-vl.service
    sudo systemctl --no-pager --full status qwen-vl.service | head -20
    ;;
  status)
    systemctl is-active qwen-vl.service vllm-ornith.service || true
    ;;
  *)
    echo "Usage: $0 {to-ornith|to-qwen|status}"
    exit 2
    ;;
esac
