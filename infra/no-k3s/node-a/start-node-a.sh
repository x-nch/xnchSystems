#!/usr/bin/env bash
# Start Node A stack: Docker (redis, postgres, litellm, langfuse) + xnch + consolidation timer.
# xnch/nexi stack only — does not start perception, vault-indexer, or k3s workloads.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${REPO_ROOT:-$HOME/xnchSystems}"
COMPOSE_DIR="$SCRIPT_DIR"
SYSTEMD_SRC="$SCRIPT_DIR/systemd"
ENV_FILE="${XNCH_ENV_FILE:-$HOME/.xnch/xnch.env}"
NODE_B_IP="${NODE_B_IP:-192.168.50.2}"

INSTALL=0
SKIP_DOCKER=0
WAIT_NODE_B=0
WAKE_NODE_B=0
RESTART_LITELLM=1

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

Start the xnch control-plane stack on Node A.

Options:
  --install       Copy systemd units to /etc/systemd/system and daemon-reload
  --skip-docker   Only restart xnch + consolidation timer (skip docker compose)
  --wake-node-b   Send WoL to xnch-core (Node B) and wait for ping (gate7 only)
  --wait-node-b   Wait for Node B vLLM (:8082) before finishing
  --no-litellm-restart  Skip 'docker compose restart litellm' after compose up
  -h, --help      Show this help

Services started:
  docker: litellm, redis, postgres-pgvector, langfuse, langfuse-postgres
  systemd: xnch.service, consolidation.timer
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --install) INSTALL=1 ;;
    --skip-docker) SKIP_DOCKER=1 ;;
    --wait-node-b) WAIT_NODE_B=1 ;;
    --wake-node-b) WAKE_NODE_B=1 ;;
    --no-litellm-restart) RESTART_LITELLM=0 ;;
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
command -v docker >/dev/null || fail "docker not installed"
docker info >/dev/null 2>&1 || fail "docker daemon not running"
[[ -f "$ENV_FILE" ]] || fail "missing $ENV_FILE"
[[ -x "$REPO_ROOT/xnch/.venv/bin/uvicorn" ]] || fail "missing xnch venv at $REPO_ROOT/xnch/.venv"
ok "docker, env, xnch venv"

if (( INSTALL )); then
  step "Install systemd units"
  sudo cp "$SYSTEMD_SRC/xnch.service" "$SYSTEMD_SRC/consolidation.service" \
         "$SYSTEMD_SRC/consolidation.timer" /etc/systemd/system/
  sudo systemctl daemon-reload
  ok "systemd units installed"
fi

if (( ! SKIP_DOCKER )); then
  step "Docker Compose"
  cd "$COMPOSE_DIR"
  docker compose up -d
  ok "docker compose up -d"

  step "Wait for containers"
  wait_http "http://localhost:4000/health/liveliness" "litellm :4000" 90
  wait_http "http://localhost:3000/api/public/health" "langfuse :3000" 120
  docker exec redis redis-cli ping | grep -q PONG && ok "redis :6379" || fail "redis :6379"
  docker exec postgres-pgvector pg_isready -U xnch -d xnch >/dev/null && ok "postgres :5432" || fail "postgres :5432"

  if (( RESTART_LITELLM )); then
    step "Reload LiteLLM config"
    docker compose restart litellm
    wait_http "http://localhost:4000/health/liveliness" "litellm after restart" 90
    ok "litellm restarted"
  fi
fi

step "systemd: xnch + consolidation"
sudo systemctl enable xnch.service consolidation.timer
sudo systemctl start xnch.service consolidation.timer
wait_http "http://localhost:8001/health" "xnch :8001" 60
systemctl is-active --quiet consolidation.timer && ok "consolidation.timer" || fail "consolidation.timer"

if (( WAKE_NODE_B )); then
  step "Wake Node B (xnch-core)"
  "$SCRIPT_DIR/wake-node-b.sh"
fi

if (( WAIT_NODE_B )); then
  step "Wait for Node B vLLM"
  wait_http "http://${NODE_B_IP}:8082/health" "vllm on Node B :8082" 180
fi

step "Summary"
docker compose -f "$COMPOSE_DIR/docker-compose.yml" ps --format 'table {{.Name}}\t{{.Status}}' 2>/dev/null | sed 's/^/  /' || true
systemctl is-active xnch.service consolidation.timer | awk '{print "  systemd:", $0}'
echo ""
echo "Node A stack is up. Run e2e test after Node B: $REPO_ROOT/infra/no-k3s/e2e-test.sh"
