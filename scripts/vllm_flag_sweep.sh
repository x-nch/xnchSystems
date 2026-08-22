#!/usr/bin/env bash
# Scripted vLLM ornith flag sweep — do NOT use OpenEvolve (search space too small).
# Run on Node B. Baseline (current unit): gpu-mem 0.95, seqs 2, max-model-len 32768.
set -euo pipefail

UNIT="${UNIT:-vllm-ornith.service}"
PORT="${PORT:-8082}"
MODEL_NAME="${MODEL_NAME:-ornith-1.0-35b}"
OUT_DIR="${OUT_DIR:-/tmp/vllm-flag-sweep}"
mkdir -p "$OUT_DIR"

# Grid (subset). Extend carefully — each cell costs a full model reload.
GPU_MEMS=(0.90 0.92 0.95 0.97)
SEQS=(1 2)
CPU_OFFLOAD=(0 8)
KV_CACHE_DTYPES=("" "fp8")

measure() {
  local label="$1"
  local url="http://127.0.0.1:${PORT}/v1/chat/completions"
  local t0 t1
  t0=$(date +%s%3N)
  curl -sS -m 120 "$url" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer xnch-vllm-key" \
    -d "{\"model\":\"${MODEL_NAME}\",\"messages\":[{\"role\":\"user\",\"content\":\"Say ping\"}],\"max_tokens\":16}" \
    >"${OUT_DIR}/${label}.json" || echo "FAIL" >"${OUT_DIR}/${label}.err"
  t1=$(date +%s%3N)
  echo "${label},latency_ms=$((t1 - t0))" | tee -a "${OUT_DIR}/results.csv"
}

echo "label,notes" >"${OUT_DIR}/results.csv"
echo "Baseline: record current unit before editing ExecStart flags" | tee -a "${OUT_DIR}/results.csv"
measure "baseline_current_unit"

cat <<'EOF'
Next steps (manual / carefully automated):
1. For each combo of GPU_MEM × SEQS × CPU_OFFLOAD × KV_CACHE_DTYPE:
   - stop qwen-vl.service (Conflicts=)
   - patch ExecStart on vllm-ornith.service with candidate flags
   - systemctl daemon-reload && systemctl restart vllm-ornith.service
   - wait until /health or first token succeeds
   - measure() tokens/s at short prompt; optionally longer contexts
2. Keep only flags that win on tokens/s + VRAM headroom + p95
3. Commit winning flags into infra/no-k3s/node-b/systemd/vllm-ornith.service

Missing flags still worth trying (not in unit today):
  --kv-cache-dtype fp8
  --cpu-offload-gb {0,8,16}
  --kv-offloading-size <N>

Do not invoke OpenEvolve for this 5-D grid.
EOF

echo "Sweep scaffold ready under ${OUT_DIR}"
