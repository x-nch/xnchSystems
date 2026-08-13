#!/usr/bin/env bash
# Node B provisioning agent — drives the vision media stack setup over SSH
# (sshpass). Step-gated: runs autonomously through setup + model download
# (S1-S7), then HALTS before the destructive phase (S8-S10) and waits for
# explicit `--resume`.
#
# Credentials come from ~/.xnch/node-b.env (NODE_B_HOST, NODE_B_USER, SSH_PASS)
# or the NODE_B_* / SSH_PASS env vars. Never store secrets in the repo.
#
# Usage:
#   scripts/media-node-b-agent.sh --background   # nohup + log, run S1-S7
#   scripts/media-node-b-agent.sh --resume       # run gated S8-S10
#   scripts/media-node-b-agent.sh --step N       # start at step N (setup)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$REPO_ROOT/scripts/logs"
LOG="$LOG_DIR/node-b-agent.log"
ENV_FILE="${NODE_B_ENV_FILE:-$HOME/.xnch/node-b.env}"
STATE_DIR="$HOME/.xnch/agent"
GATE_MARKER="$STATE_DIR/gate-s7"
TOKEN_FILE="$STATE_DIR/media-token"

mkdir -p "$LOG_DIR" "$STATE_DIR"

START_FROM=1
RESUME=0
BACKGROUND=0

usage() {
  sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'
}

ORIG_ARGS=("$@")

while [[ $# -gt 0 ]]; do
  case "$1" in
    --background) BACKGROUND=1; shift ;;
    --resume) RESUME=1; START_FROM=8; shift ;;
    --step) START_FROM="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

if (( BACKGROUND )); then
  BG_ARGS=()
  for a in "${ORIG_ARGS[@]}"; do
    [[ "$a" != "--background" ]] && BG_ARGS+=("$a")
  done
  nohup "$0" "${BG_ARGS[@]}" >> "$LOG" 2>&1 < /dev/null &
  echo "agent started in background (pid $!); tail -f scripts/logs/node-b-agent.log"
  exit 0
fi

[[ -f "$ENV_FILE" ]] && source "$ENV_FILE"
: "${NODE_B_HOST:?set NODE_B_HOST (or ~/.xnch/node-b.env)}"
: "${NODE_B_USER:?set NODE_B_USER}"
: "${SSH_PASS:?set SSH_PASS}"

SSH_OPTS=(-o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=/dev/null \
  -o ConnectTimeout=10 -o ServerAliveInterval=30 -o ServerAliveCountMax=4)

ssh_node() {
  sshpass -p "$SSH_PASS" ssh "${SSH_OPTS[@]}" "$NODE_B_USER@$NODE_B_HOST" "$@"
}
rsync_node() {
  sshpass -p "$SSH_PASS" rsync -az --exclude __pycache__ --exclude .pytest_cache \
    -e "ssh ${SSH_OPTS[*]}" "$@"
}

log() { echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }
step() { echo "" | tee -a "$LOG"; echo "=== $1 ===" | tee -a "$LOG"; }
ok() { echo "  OK  $1" | tee -a "$LOG"; }
warn() { echo "  WARN $1" | tee -a "$LOG"; }
fail() { echo "  FAIL $1" | tee -a "$LOG"; exit 1; }

# Run a command remotely under nohup, poll for a completion marker. The remote
# process survives the SSH connection, so a dropped link can't kill the work.
remote_bg() {
  local name="$1" timeout_s="$2"; shift 2
  local rlog="/tmp/agent-$name.log" done="/tmp/agent-$name.done"
  ssh_node "rm -f '$done'; nohup bash -lc 'set -euo pipefail; $*; echo OK > $done' > '$rlog' 2>&1 || echo FAIL > '$done' &" \
    || fail "launch $name failed"
  log "  launched remote '$name' (timeout ${timeout_s}s)"
  local waited=0
  while (( waited < timeout_s )); do
    if ssh_node "test -f '$done'" >/dev/null 2>&1; then
      local result
      result=$(ssh_node "cat '$done'")
      echo "  [$name] result=$result" | tee -a "$LOG"
      ssh_node "tail -5 '$rlog'" | tee -a "$LOG"
      [[ "$result" == "OK" ]] || fail "remote '$name' failed"
      return 0
    fi
    sleep 30
    waited=$((waited + 30))
  done
  fail "remote '$name' timed out (${timeout_s}s)"
}

s1_preflight() {
  step "S1 preflight"
  ssh_node 'nvidia-smi --query-gpu=name,memory.total --format=csv,noheader' | tee -a "$LOG" || fail "nvidia-smi failed"
  ssh_node 'df -h ~ | tail -1' | tee -a "$LOG"
  ssh_node 'sudo -n true' >/dev/null 2>&1 || fail "passwordless sudo unavailable"
  ssh_node 'curl -sfI -m 8 https://huggingface.co >/dev/null && echo HF-ok' | tee -a "$LOG" | grep -q HF-ok || warn "HF unreachable from Node B"
  ok "preflight"
}

s2_sync() {
  step "S2 sync repo paths to Node B"
  rsync_node "$REPO_ROOT/media-gateway" "$NODE_B_USER@$NODE_B_HOST:~/xnchSystems/" | tee -a "$LOG"
  rsync_node "$REPO_ROOT/infra/no-k3s/node-b" "$NODE_B_USER@$NODE_B_HOST:~/xnchSystems/infra/no-k3s/" | tee -a "$LOG"
  rsync_node "$REPO_ROOT/infra/no-k3s/media-e2e.sh" "$NODE_B_USER@$NODE_B_HOST:~/xnchSystems/infra/no-k3s/" | tee -a "$LOG"
  rsync_node "$REPO_ROOT/xnch/litellm_config.yaml" "$NODE_B_USER@$NODE_B_HOST:~/xnchSystems/xnch/" | tee -a "$LOG"
  ok "synced"
}

s3_venvs() {
  step "S3 venv skeletons"
  ssh_node 'for v in vllm-qwen-vl comfy media-gateway; do test -x ~/venvs/$v/bin/python || /usr/bin/python3 -m venv ~/venvs/$v; done' | tee -a "$LOG"
  ok "venvs created"
}

s4_comfy() {
  step "S4 ComfyUI + GGUF nodes"
  ssh_node 'test -d ~/ComfyUI || git clone -q https://github.com/comfyanonymous/ComfyUI ~/ComfyUI' | tee -a "$LOG"
  ssh_node 'test -d ~/ComfyUI/custom_nodes/ComfyUI-GGUF || git clone -q https://github.com/city96/ComfyUI-GGUF ~/ComfyUI/custom_nodes/ComfyUI-GGUF' | tee -a "$LOG"
  ssh_node 'test -f ~/ComfyUI/main.py && test -f ~/ComfyUI/custom_nodes/ComfyUI-GGUF/__init__.py' | tee -a "$LOG" \
    || fail "ComfyUI / GGUF node missing"
  ok "comfyui + gguf"
}

s5_deps() {
  step "S5 venv dependencies"
  remote_bg comfy-deps 1800 \
    "~/venvs/comfy/bin/pip install -q --upgrade pip && \
     ~/venvs/comfy/bin/pip install -q huggingface_hub && \
     ~/venvs/comfy/bin/pip install -q torch torchvision --index-url https://download.pytorch.org/whl/cu128 && \
     ~/venvs/comfy/bin/pip install -q -r ~/ComfyUI/requirements.txt && \
     ~/venvs/comfy/bin/pip install -q -r ~/ComfyUI/custom_nodes/ComfyUI-GGUF/requirements.txt"
  ok "comfy deps"

  remote_bg gw-deps 600 \
    "~/venvs/media-gateway/bin/pip install -q --upgrade pip && \
     ~/venvs/media-gateway/bin/pip install -q -r ~/xnchSystems/media-gateway/requirements.txt"
  ok "gateway deps"

  remote_bg vllm-deps 2400 \
    "~/venvs/vllm-qwen-vl/bin/pip install -q --upgrade pip && ~/venvs/vllm-qwen-vl/bin/pip install -q vllm"
  ok "vllm deps"
}

s6_env() {
  step "S6 media.env"
  local token=""
  if ssh_node 'test -f ~/.xnch/media.env' >/dev/null 2>&1; then
    token=$(ssh_node 'grep "^MEDIA_GATEWAY_TOKEN=" ~/.xnch/media.env | cut -d= -f2')
  fi
  [[ -n "$token" ]] || token="$(uuidgen | tr -d - | cut -c1-32)"
  local content
  content="MEDIA_GATEWAY_TOKEN=$token
MEDIA_GATEWAY_BIND=$NODE_B_HOST
MEDIA_GATEWAY_PORT=8090
MEDIA_GATEWAY_COMFY_URL=http://127.0.0.1:8188
MEDIA_GATEWAY_COMFY_INPUT_DIR=/home/$NODE_B_USER/ComfyUI/input
MEDIA_GATEWAY_COMFY_OUTPUT_DIR=/home/$NODE_B_USER/ComfyUI/output
MEDIA_GATEWAY_WORKFLOWS_DIR=/home/$NODE_B_USER/xnchSystems/media-gateway/workflows
MEDIA_GATEWAY_LITELLM_URL=http://127.0.0.1:8083/v1
MEDIA_GATEWAY_LITELLM_KEY=
MEDIA_GATEWAY_QWEN_MODEL=qwen2.5-vl-7b
LANGFUSE_PUBLIC_KEY=${LANGFUSE_PUBLIC_KEY:-}
LANGFUSE_SECRET_KEY=${LANGFUSE_SECRET_KEY:-}
LANGFUSE_HOST=${LANGFUSE_HOST:-https://cloud.langfuse.com}"
  printf '%s\n' "$content" | ssh_node 'mkdir -p ~/.xnch && umask 077 && cat > ~/.xnch/media.env && echo written' | tee -a "$LOG"
  printf '%s' "$token" > "$TOKEN_FILE"
  chmod 600 "$TOKEN_FILE"
  ok "media.env written (token $token)"
}

s7_download() {
  step "S7 model downloads"
  remote_bg models 10800 "
    set -e
    HF=~/venvs/comfy/bin/hf
    test -x \$HF || HF=~/venvs/comfy/bin/huggingface-cli
    mkdir -p ~/models/comfy/diffusion_models ~/models/comfy/clip ~/models/comfy/vae ~/models/comfy/_dl
    if ! test -f ~/models/Qwen2.5-VL-7B-Instruct-AWQ/config.json; then
      \$HF download Qwen/Qwen2.5-VL-7B-Instruct-AWQ --local-dir ~/models/Qwen2.5-VL-7B-Instruct-AWQ
    fi
    \$HF download Comfy-Org/flux1-schnell --local-dir ~/models/comfy/_dl/flux --include '*.safetensors'
    mv -f ~/models/comfy/_dl/flux/flux1-schnell-fp8.safetensors ~/models/comfy/diffusion_models/
    mv -f ~/models/comfy/_dl/flux/ae.safetensors ~/models/comfy/vae/
    \$HF download Comfy-Org/flux_text_encoders --local-dir ~/models/comfy/_dl/flux_te --include '*.safetensors'
    mv -f ~/models/comfy/_dl/flux_te/t5xxl_fp8_e4m3fn.safetensors ~/models/comfy/clip/
    mv -f ~/models/comfy/_dl/flux_te/clip_l.safetensors ~/models/comfy/clip/
    \$HF download city96/Wan2.1-T2V-14B-gguf --local-dir ~/models/comfy/_dl/wan_t2v --include '*.Q5_K_M.gguf'
    mv -f ~/models/comfy/_dl/wan_t2v/wan2.1-t2v-14b-Q5_K_M.gguf ~/models/comfy/diffusion_models/
    \$HF download city96/Wan2.1-I2V-14B-480P-gguf --local-dir ~/models/comfy/_dl/wan_i2v --include '*.Q5_K_M.gguf'
    mv -f ~/models/comfy/_dl/wan_i2v/wan2.1-i2v-14b-480p-Q5_K_M.gguf ~/models/comfy/diffusion_models/
    \$HF download Comfy-Org/Wan_2.1_ComfyUI_repackaged --local-dir ~/models/comfy/_dl/wan21 \
      --include 'split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors' \
      --include 'split_files/vae/wan_2.1_vae.safetensors'
    mv -f ~/models/comfy/_dl/wan21/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors ~/models/comfy/clip/
    mv -f ~/models/comfy/_dl/wan21/split_files/vae/wan_2.1_vae.safetensors ~/models/comfy/vae/
    rm -rf ~/models/comfy/_dl
    du -sh ~/models/comfy ~/models/Qwen2.5-VL-7B-Instruct-AWQ
  "
  ok "models downloaded"
}

s8_stop() {
  step "S8 stop exclusivity services"
  ssh_node 'systemctl stop vllm-ornith.service nexi.service' | tee -a "$LOG"
  ssh_node 'systemctl is-active vllm-ornith.service nexi.service' | tee -a "$LOG" | grep -q inactive || fail "services still active"
  ok "ornith + nexi stopped"
}

s9_start() {
  step "S9 start vision stack"
  ssh_node 'cd ~/xnchSystems/infra/no-k3s/node-b && ./start-media.sh --install --force' | tee -a "$LOG"
  ok "stack started"
}

s10_verify() {
  step "S10 verify"
  ssh_node 'curl -sf http://localhost:8090/health' | tee -a "$LOG" || fail "gateway not healthy"
  ssh_node 'curl -sf http://localhost:8188/system_stats >/dev/null && echo comfy-ok' | tee -a "$LOG" | grep -q comfy-ok || fail "comfy not healthy"
  ssh_node 'curl -sf http://localhost:8083/health' | tee -a "$LOG" || fail "qwen-vl not healthy"
  if curl -sf "http://$NODE_B_HOST:8090/health" >/dev/null 2>&1; then
    ok "gateway reachable from Mac at $NODE_B_HOST:8090"
  else
    warn "gateway not reachable from Mac (check firewall)"
  fi
  if [[ "${SKIP_E2E:-0}" == "1" ]]; then
    warn "skipping e2e (SKIP_E2E=1)"
    return 0
  fi
  remote_bg e2e 7200 \
    "cd ~/xnchSystems && MEDIA_E2E_GATEWAY=http://127.0.0.1:8090 MEDIA_E2E_ENV=~/.xnch/media.env ./infra/no-k3s/media-e2e.sh"
  ok "e2e passed"
}

run() {
  local end="$1"
  for n in $(seq "$START_FROM" "$end"); do
    case $n in
      1) s1_preflight ;;
      2) s2_sync ;;
      3) s3_venvs ;;
      4) s4_comfy ;;
      5) s5_deps ;;
      6) s6_env ;;
      7) s7_download ;;
      8) s8_stop ;;
      9) s9_start ;;
      10) s10_verify ;;
    esac
  done
}

if (( RESUME == 0 )); then
  log "agent start (setup phase, steps $START_FROM-7)"
  run 7
  step "⛔ GATE — setup + download complete. Approve to stop vllm-ornith/nexi and start the stack."
  echo "  resume with: scripts/media-node-b-agent.sh --resume" | tee -a "$LOG"
  echo "gated" > "$GATE_MARKER"
  log "agent halted at gate"
else
  log "agent resume (gated phase, steps $START_FROM-10)"
  [[ -f "$GATE_MARKER" ]] || warn "no gate marker found — running S8-S10 anyway"
  run 10
  rm -f "$GATE_MARKER"
  log "agent complete"
fi
