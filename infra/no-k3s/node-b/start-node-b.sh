#!/usr/bin/env bash
# Start Node B stack: vLLM Ornith + nexi (xnch/nexi stack only).
# Does not start local redis/postgres, k3s-agent, vllm-quality, or vllm-qwen.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${REPO_ROOT:-$HOME/xnchSystems}"
SYSTEMD_SRC="$SCRIPT_DIR/systemd"
ENV_FILE="${NEXI_ENV_FILE:-$HOME/.xnch/nexi.env}"
NODE_A_IP="${NODE_A_IP:-192.168.50.1}"
VLLM_MODEL_PATH="${VLLM_MODEL_PATH:-$HOME/models/ornith-gptq-pro}"
VLLM_VENV="${VLLM_VENV:-$HOME/venvs/vllm-ornith}"

INSTALL=0
SKIP_VLLM=0
WAIT_NODE_A=1

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

Start the nexi inference stack on Node B.

Options:
  --install       Copy systemd units to /etc/systemd/system and daemon-reload
  --skip-vllm     Only restart nexi (vLLM must already be running)
  --no-wait-node-a  Skip preflight checks against Node A
  -h, --help      Show this help

Services started (in order):
  1. vllm-ornith.service  (:8082)
  2. nexi.service         (:8000)

Node A dependencies (must be reachable for nexi):
  redis :6379, postgres :5432, xnch :8001, litellm :4000
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --install) INSTALL=1 ;;
    --skip-vllm) SKIP_VLLM=1 ;;
    --no-wait-node-a) WAIT_NODE_A=0 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
  esac
  shift
done

step() { echo ""; echo "=== $1 ==="; }
ok()   { echo "  OK  $1"; }
fail() { echo "  FAIL $1" >&2; exit 1; }

wait_http() {
  local url="$1" label="$2" max="${3:-60}"
  local i=0
  while (( i < max )); do
    if curl -sf "$url" >/dev/null 2>&1; then
      ok "$label"
      return 0
    fi
    sleep 2
    (( i += 2 )) || true
  done
  fail "$label (timeout ${max}s)"
}

step "Preflight"
[[ -f "$ENV_FILE" ]] || fail "missing $ENV_FILE"
[[ -d "$VLLM_MODEL_PATH" ]] || fail "missing vLLM model at $VLLM_MODEL_PATH"
[[ -x "$VLLM_VENV/bin/vllm" ]] || fail "missing vLLM venv at $VLLM_VENV"
[[ -x "$REPO_ROOT/nexi/.venv/bin/uvicorn" ]] || fail "missing nexi venv at $REPO_ROOT/nexi/.venv"
ok "env, model, venvs"

if (( WAIT_NODE_A )); then
  step "Node A dependencies"
  wait_http "http://${NODE_A_IP}:8001/health" "xnch on Node A :8001" 30
  wait_http "http://${NODE_A_IP}:4000/health/liveliness" "litellm on Node A :4000" 30
  # redis/postgres: best-effort via docker on node-a from nexi env
  ok "Node A reachable"
fi

if (( INSTALL )); then
  step "Install systemd units"
  sudo cp "$SYSTEMD_SRC/vllm-ornith.service" "$SYSTEMD_SRC/nexi.service" /etc/systemd/system/
  sudo systemctl daemon-reload
  ok "systemd units installed"
fi

if (( ! SKIP_VLLM )); then
  step "vLLM Ornith"
  sudo systemctl enable vllm-ornith.service
  sudo systemctl start vllm-ornith.service
  wait_http "http://localhost:8082/health" "vllm-ornith :8082" 300
fi

step "nexi"
sudo systemctl enable nexi.service
sudo systemctl start nexi.service
wait_http "http://localhost:8000/health" "nexi :8000" 60

step "Summary"
systemctl is-active vllm-ornith.service nexi.service | awk '{print "  systemd:", $0}'
echo ""
echo "Node B stack is up. Validate from Node A: $REPO_ROOT/infra/no-k3s/e2e-test.sh"
