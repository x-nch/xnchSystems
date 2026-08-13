#!/usr/bin/env bash
# Start the vision media stack on Node B: Qwen2.5-VL (vLLM :8083) + ComfyUI (:8188)
# + media-gateway (:8090). Runs standalone — the 3090 is dedicated to this stack.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${REPO_ROOT:-$HOME/xnchSystems}"
SYSTEMD_SRC="$SCRIPT_DIR/systemd"
MEDIA_ENV="${MEDIA_ENV_FILE:-$HOME/.xnch/media.env}"
NODE_A_IP="${NODE_A_IP:-}"
VLLM_VENV="${VLLM_VENV:-$HOME/venvs/vllm-qwen-vl}"
VLLM_MODEL_PATH="${VLLM_MODEL_PATH:-$HOME/models/Qwen2.5-VL-7B-Instruct-AWQ}"
COMFY_VENV="${COMFY_VENV:-$HOME/venvs/comfy}"
COMFY_SRC="${COMFY_SRC:-$HOME/ComfyUI}"
COMFY_MODELS="${COMFY_MODELS:-$HOME/models/comfy}"
GW_VENV="${GW_VENV:-$HOME/venvs/media-gateway}"
GW_SRC="${GW_SRC:-$REPO_ROOT/media-gateway}"
MIN_FREE_GB="${MIN_FREE_GB:-50}"

INSTALL=0
FORCE=0
DOWNLOAD=0
WAIT_NODE_A=1

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

Start the vision media stack on Node B (RTX 3090).

Options:
  --install          Copy systemd units to /etc/systemd/system and daemon-reload
  --force            Skip the exclusivity stop-offer for active services
                     (NOT recommended — GPU becomes shared)
  --download-models  Download model weights (gated by prompt) — needs ~${MIN_FREE_GB}GB free
  --no-wait-node-a   Skip reachability checks against Node A
  -h, --help         Show this help

Exclusivity: vllm-ornith.service and nexi.service must be stopped before this
stack starts (systemd Conflicts= is the backstop). The script OFFERS to stop
them; it never does so silently. Node A xnch must be stopped manually on Node A.

Services started (in order):
  1. qwen-vl.service        (:8083, vLLM Qwen2.5-VL-7B-AWQ)
  2. comfy-ui.service       (:8188, Flux + Wan 2.2)
  3. media-gateway.service  (:8090, REST orchestrator)
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --install) INSTALL=1 ;;
    --force) FORCE=1 ;;
    --download-models) DOWNLOAD=1 ;;
    --no-wait-node-a) WAIT_NODE_A=0 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
  esac
  shift
done

step() { echo ""; echo "=== $1 ==="; }
ok()   { echo "  OK  $1"; }
warn() { echo "  WARN $1"; }
fail() { echo "  FAIL $1" >&2; exit 1; }

wait_http() {
  local url="$1" label="$2" max="${3:-120}"
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

# Offer (never silently) to stop a service that would share the 3090.
require_stopped() {
  local svc="$1" label="$2"
  if systemctl is-active --quiet "$svc" 2>/dev/null; then
    if (( FORCE )); then
      warn "$label is active; --force set, continuing WITHOUT stopping it (GPU shared — not recommended)."
      return 0
    fi
    echo "  $label is active (systemctl is-active $svc)."
    read -r -p "  Stop $svc now? [y/N] " ans
    if [[ "$ans" =~ ^[Yy]$ ]]; then
      sudo systemctl stop "$svc"
      ok "stopped $svc"
    else
      fail "refusing to start while $svc is active (pass --force to override)"
    fi
  else
    ok "$label stopped"
  fi
}

disk_free_gb() {
  df -Pk "$HOME" | awk 'NR==2 { printf "%d", $4/1024/1024 }'
}

download_models() {
  local free
  free="$(disk_free_gb)"
  echo "  Disk free on $HOME: ${free}GB (need >= ${MIN_FREE_GB}GB)"
  (( free >= MIN_FREE_GB )) || fail "not enough free disk; freeing ${MIN_FREE_GB}GB+ required"
  if [[ -x "$COMFY_VENV/bin/hf" ]]; then
    HFCLI="$COMFY_VENV/bin/hf"
  elif [[ -x "$COMFY_VENV/bin/huggingface-cli" ]]; then
    HFCLI="$COMFY_VENV/bin/huggingface-cli"
  else
    fail "no hf / huggingface-cli in $COMFY_VENV — install huggingface_hub first"
  fi

  echo ""
  echo "  Will download (gated by your approval):"
  echo "    1. Qwen/Qwen2.5-VL-7B-Instruct-AWQ          -> $VLLM_MODEL_PATH"
  echo "    2. Comfy-Org/flux1-schnell (fp8) + VAE      -> $COMFY_MODELS/flux  (non-gated; FLUX.1-dev needs license acceptance)"
  echo "    3. Comfy-Org/flux_text_encoders (t5xxl+clip_l) -> $COMFY_MODELS/flux"
  echo "    4. city96/Wan2.1-T2V-14B-gguf Q5_K_M        -> $COMFY_MODELS/wan"
  echo "    5. city96/Wan2.1-I2V-14B-480P-gguf Q5_K_M   -> $COMFY_MODELS/wan"
  echo "    6. Comfy-Org/Wan_2.1_ComfyUI_repackaged (umt5+wan_2.1_vae) -> $COMFY_MODELS/wan"
  echo "    HF_ENDPOINT=${HF_ENDPOINT:-<unset, default hub>}"
  read -r -p "  Proceed with model download? [y/N] " ans
  [[ "$ans" =~ ^[Yy]$ ]] || { echo "  Skipping model download."; return 0; }

  mkdir -p "$COMFY_MODELS"
  local HF=""
  [[ -n "${HF_ENDPOINT:-}" ]] && HF="--endpoint $HF_ENDPOINT"

  step "Model download: Qwen2.5-VL (AWQ)"
  "$HFCLI" download $HF Qwen/Qwen2.5-VL-7B-Instruct-AWQ \
    --local-dir "$VLLM_MODEL_PATH"

  step "Model download: Flux (schnell fp8) + text encoders"
  "$HFCLI" download $HF Comfy-Org/flux1-schnell \
    --local-dir "$COMFY_MODELS/flux"
  "$HFCLI" download $HF Comfy-Org/flux_text_encoders \
    --local-dir "$COMFY_MODELS/flux"

  step "Model download: Wan 2.1 (GGUF Q5) + text encoder/VAE"
  "$HFCLI" download $HF city96/Wan2.1-T2V-14B-gguf \
    --local-dir "$COMFY_MODELS/wan" --include "*Q5_K_M.gguf"
  "$HFCLI" download $HF city96/Wan2.1-I2V-14B-480P-gguf \
    --local-dir "$COMFY_MODELS/wan" --include "*Q5_K_M.gguf"
  "$HFCLI" download $HF Comfy-Org/Wan_2.1_ComfyUI_repackaged \
    --local-dir "$COMFY_MODELS/wan" \
    --include "split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors" \
    --include "split_files/vae/wan_2.1_vae.safetensors"
  ok "models downloaded"
}

step "Preflight"
[[ -f "$MEDIA_ENV" ]] || fail "missing $MEDIA_ENV — create it with: MEDIA_GATEWAY_TOKEN, MEDIA_GATEWAY_BIND, MEDIA_GATEWAY_COMFY_URL/INPUT_DIR/OUTPUT_DIR, MEDIA_GATEWAY_LITELLM_URL/KEY, LANGFUSE_*"
[[ -d "$VLLM_MODEL_PATH" ]] || warn "missing Qwen-VL model at $VLLM_MODEL_PATH (use --download-models)"
[[ -x "$VLLM_VENV/bin/vllm" ]] || fail "missing vllm venv at $VLLM_VENV (python -m venv; pip install vllm)"
[[ -x "$COMFY_VENV/bin/python" ]] || fail "missing comfy venv at $COMFY_VENV"
[[ -d "$COMFY_SRC" ]] || fail "missing ComfyUI source at $COMFY_SRC (git clone https://github.com/comfyanonymous/ComfyUI)"
[[ -x "$GW_VENV/bin/python" ]] || fail "missing media-gateway venv at $GW_VENV"
[[ -d "$GW_SRC" ]] || fail "missing media-gateway source at $GW_SRC"
ok "env, venvs, source"

if (( DOWNLOAD )); then
  download_models
fi

step "GPU driver"
if ! nvidia-smi --query-gpu=name --format=csv,noheader &>/dev/null; then
  echo "  NVIDIA driver not loaded. Run once: sudo $REPO_ROOT/infra/no-k3s/node-b/setup-gpu-driver.sh && sudo reboot" >&2
  fail "nvidia-smi unavailable — see setup-gpu-driver.sh"
fi
ok "nvidia-smi"

step "Exclusivity precheck (3090 dedicated to this stack)"
require_stopped vllm-ornith.service "vLLM Ornith"
require_stopped nexi.service "Nexi engine"
if (( WAIT_NODE_A )) && [[ -n "$NODE_A_IP" ]]; then
  if curl -sf "http://${NODE_A_IP}:8001/health" >/dev/null 2>&1; then
    warn "Node A xnch (:8001) is reachable and may still route to this GPU via LiteLLM."
    if (( ! FORCE )); then
      read -r -p "  Continue anyway? [y/N] " ans
      [[ "$ans" =~ ^[Yy]$ ]] || fail "aborted — stop xnch on Node A first"
    fi
  else
    ok "Node A xnch not reachable"
  fi
fi

if (( INSTALL )); then
  step "Install systemd units"
  sudo cp "$SYSTEMD_SRC/qwen-vl.service" "$SYSTEMD_SRC/comfy-ui.service" "$SYSTEMD_SRC/media-gateway.service" /etc/systemd/system/
  sudo systemctl daemon-reload
  ok "systemd units installed"
fi

step "Start services"
sudo systemctl enable qwen-vl.service comfy-ui.service media-gateway.service
sudo systemctl start qwen-vl.service
wait_http "http://localhost:8083/health" "qwen-vl :8083" 300
sudo systemctl start comfy-ui.service
wait_http "http://localhost:8188/system_stats" "comfy-ui :8188" 120
sudo systemctl start media-gateway.service
wait_http "http://localhost:8090/health" "media-gateway :8090" 60

step "Summary"
systemctl is-active qwen-vl.service comfy-ui.service media-gateway.service | awk '{print "  systemd:", $0}'
echo ""
echo "Vision media stack is up."
echo "  Understanding (qwen-vl vLLM, direct):  model qwen2.5-vl-7b @ http://localhost:8083"
echo "  Media gateway (bearer token):        http://localhost:8090"
echo "  ComfyUI debug UI:                    http://192.168.1.9:8188"
