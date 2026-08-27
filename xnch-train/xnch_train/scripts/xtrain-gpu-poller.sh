#!/usr/bin/env bash
#
# xtrain-gpu-poller.sh — lightweight nvidia-smi polling loop (Node B only).
#
# Hardware-gated: this must ONLY run on the RTX3090 node (Node B). It polls
# nvidia-smi every $INTERVAL seconds and logs GPU state so contention (another
# unit holding the GPU), OOM, and vLLM restarts can be correlated against the
# xtrain cycle timeline.
#
# Real event emission to Langfuse is performed by the Python side
# (xnch_train.train.observability.GpuPoller), not from bash — bash here just
# produces the structured observations the Python emitter would POST as
# `gpu.contention` events. The loop is a correct, commented scaffold; wire it
# to the Python emitter when the production runtime is in place.
#
# Usage: XTRAIN_LANGFUSE_HOST=http://lf.internal ./xtrain-gpu-poller.sh

set -euo pipefail

INTERVAL="${XTRAIN_GPU_POLL_INTERVAL:-5}"          # seconds between samples
LOG_FILE="${XTRAIN_GPU_POLL_LOG:-/var/log/xtrain/gpu-poller.log}"
mkdir -p "$(dirname "$LOG_FILE")"

if ! command -v nvidia-smi >/dev/null 2>&1; then
  echo "nvidia-smi not found — this script must run on the GPU node (Node B)." >&2
  exit 1
fi

echo "xtrain-gpu-poller: sampling every ${INTERVAL}s (log: ${LOG_FILE})" >&2

while true; do
  ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

  # Query the fields we correlate against contention: who holds the GPU,
  # memory pressure, temperature, and whether the vLLM/Ornith process is up.
  sample="$(nvidia-smi \
    --query-gpu=index,name,utilization.gpu,memory.used,memory.total,temperature.gpu \
    --format=csv,noheader,nounits \
    2>/dev/null || true)"

  if [ -z "$sample" ]; then
    echo "${ts} event=no_sample" >>"$LOG_FILE"
  else
    echo "${ts} ${sample}" >>"$LOG_FILE"
  fi

  # Contention marker: the Vision Media Stack and Ornith share the GPU via
  # systemd Conflicts=. A non-zero compute-app count that is not the expected
  # Ornith/vLLM pid is a contention signal worth emitting as gpu.contention.
  procs="$(nvidia-smi \
    --query-compute-apps=pid,process_name,used_memory \
    --format=csv,noheader 2>/dev/null || true)"
  if [ -n "$procs" ]; then
    echo "${ts} compute-apps=${procs}" >>"$LOG_FILE"
  fi

  sleep "$INTERVAL"
done
