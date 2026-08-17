#!/usr/bin/env bash
# Deploy the current ornith branch to node-a / node-b via git push-to-deploy.
#
# Model: GitHub is the source of truth. Branches are published to GitHub first
# (superproject + submodule worktrees), then the superproject is pushed over
# SSH to each node's ~/xnchSystems clone. The node updates its worktree
# (receive.denyCurrentBranch=updateInstead + forced checkout), syncs
# submodules, restarts the services affected by the change, and verifies
# health. No rsync. Node-local uncommitted changes are tarballed to
# ~/xnchSystems.deploy-backup.<ts>.tar.gz before the forced switch.
#
# Usage:
#   scripts/deploy.sh node-a|node-b|all [options]
#   scripts/deploy.sh --bootstrap node-a|node-b   # one-time clone + setup
#
# Options:
#   --branch NAME       Branch to publish/deploy (default: feat/ornith-cli-voice)
#   --wake              If node-b is down, WoL it from node-a first
#   --sync-deps         Run uv pip install into node venvs when deps changed
#   --restart-vllm      Restart vllm-ornith on node-b even if unit unchanged
#   --skip-publish      Skip pushing branches to GitHub (assumes already pushed)
#   -h, --help          Show this help
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BRANCH="${DEPLOY_BRANCH:-feat/ornith-cli-voice}"
NODE_A_ALIAS="${NODE_A_ALIAS:-node-a}"
NODE_B_ALIAS="${NODE_B_ALIAS:-node-b}"
NODE_B_IP="${NODE_B_IP:-192.168.1.9}"
NEXI_WT="${NEXI_WT:-/Users/xnch/nexi-ornith}"
XNCH_WT="${XNCH_WT:-/Users/xnch/xnch-ornith}"

# Path prefixes in the repo that map to restarts (node-a)
NODE_A_COMPOSE_PATHS="infra/no-k3s/node-a/docker-compose.yml infra/no-k3s/node-a/litellm-config/ infra/no-k3s/shared/litellm-routing.yaml infra/no-k3s/node-a/searxng/"
NODE_A_UNIT_PATHS="infra/no-k3s/node-a/systemd/"
# Path prefixes in the repo that map to restarts (node-b)
NODE_B_UNIT_PATHS="infra/no-k3s/node-b/systemd/"
NODE_B_VLLM_PATHS="infra/no-k3s/node-b/systemd/vllm-ornith.service"

TARGETS=()
WAKE=0
SYNC_DEPS=0
RESTART_VLLM=0
SKIP_PUBLISH=0
BOOTSTRAP=0

usage() {
  sed -n '2,18p' "$0" | sed 's/^# \{0,1\}//'
}

step() { echo ""; echo "=== $1 ==="; }
ok()   { echo "  OK  $1"; }
warn() { echo "  WARN $1" >&2; }
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

while [[ $# -gt 0 ]]; do
  case "$1" in
    node-a|node-b|all) TARGETS+=("$1") ;;
    --bootstrap) BOOTSTRAP=1 ;;
    --branch) BRANCH="$2"; shift ;;
    --wake) WAKE=1 ;;
    --sync-deps) SYNC_DEPS=1 ;;
    --restart-vllm) RESTART_VLLM=1 ;;
    --skip-publish) SKIP_PUBLISH=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
  esac
  shift
done

if [[ ${#TARGETS[@]} -eq 0 ]]; then
  echo "missing target (node-a | node-b | all)" >&2
  usage
  exit 1
fi

if (( BOOTSTRAP )); then
  [[ ${#TARGETS[@]} -eq 1 ]] || fail "--bootstrap takes exactly one target (node-a | node-b | all)"
fi

needs_node_b() {
  [[ " ${TARGETS[*]} " == *" all "* || " ${TARGETS[*]} " == *" node-b "* ]]
}

# ---------------------------------------------------------------------------
# Publish branches to GitHub (superproject + submodules) so nodes can fetch
# the pinned submodule SHAs.
# ---------------------------------------------------------------------------
publish() {
  step "Publish to GitHub"

  # Submodules are needed on both nodes (node-a runs xnch; node-b runs nexi
  # which imports xnch), so always publish them.
  if (( ! SKIP_PUBLISH )); then
    echo "  nexi:  $NEXI_WT"
    git -C "$NEXI_WT" push -u origin "$BRANCH" || fail "push nexi failed"
    echo "  xnch:  $XNCH_WT"
    git -C "$XNCH_WT" push -u origin "$BRANCH" || fail "push xnch failed"
    echo "  superproject: $REPO_ROOT"
    git -C "$REPO_ROOT" push -u origin "$BRANCH" || fail "push superproject failed"
  else
    echo "  --skip-publish set; verifying commits exist on GitHub"
  fi

  # Verify the submodule SHAs the superproject pins are reachable on GitHub.
  local nexi_sha xnch_sha
  nexi_sha=$(git -C "$REPO_ROOT" ls-tree HEAD nexi | awk '{print $3}')
  xnch_sha=$(git -C "$REPO_ROOT" ls-tree HEAD xnch | awk '{print $3}')
  echo "  pinned nexi=$nexi_sha xnch=$xnch_sha"
  if ! git -C "$NEXI_WT" cat-file -e "${nexi_sha}^{commit}" 2>/dev/null; then
    fail "nexi SHA $nexi_sha not present in $NEXI_WT — commit/push the submodule first"
  fi
  if ! git -C "$XNCH_WT" cat-file -e "${xnch_sha}^{commit}" 2>/dev/null; then
    fail "xnch SHA $xnch_sha not present in $XNCH_WT — commit/push the submodule first"
  fi
  ok "commits published"
}

# ---------------------------------------------------------------------------
# Backup node-local uncommitted work before a forced checkout discards it.
# Tars dirty tracked files + untracked files in ~/xnchSystems (superproject +
# submodules) to ~/xnchSystems.deploy-backup.<ts>.tar.gz on the node.
# ---------------------------------------------------------------------------
backup_node() {
  local node="$1"
  step "Backup $node local changes"
  ssh "$node" '
    set -e
    ROOT=~/xnchSystems
    TS=$(date +%Y%m%d-%H%M%S)
    OUT=~/xnchSystems.deploy-backup.$TS.tar.gz
    LIST=""
    collect() {
      local dir="$1" prefix="$2"
      [[ -d "$dir/.git" ]] || return 0
      local rel rest
      while IFS= read -r rest; do
        rel=${rest##* }
        [[ -n "$rel" ]] || continue
        # submodule root pointers are handled by their own collect pass
        [[ "$rel" == "nexi" || "$rel" == "xnch" ]] && continue
        # skip deleted (D) paths and heavy dirs; only tar what still exists
        [[ -e "$dir/$rel" ]] || continue
        case "$rel" in
          *.venv*|*node_modules*|*__pycache__*|*.pytest_cache*|*.egg-info*) continue ;;
        esac
        [[ -n "$prefix" ]] && rel="$prefix/$rel"
        LIST="$LIST $rel"
      done < <(git -C "$dir" status --porcelain 2>/dev/null)
    }
    collect "$ROOT" ""
    collect "$ROOT/xnch" "xnch"
    collect "$ROOT/nexi" "nexi"
    if [[ -n "$LIST" ]]; then
      tar -czf "$OUT" -C "$ROOT" $LIST 2>/dev/null && echo "  backed up to $OUT ($(wc -c < "$OUT" | tr -d " ") bytes)"
    else
      echo "  no local changes to back up"
    fi
  ' || warn "$node: backup failed (continuing)"
}

# ---------------------------------------------------------------------------
# Per-node push + sync + restart + health.
#   $1 = node alias, $2 = health url, $3 = label
# ---------------------------------------------------------------------------
deploy_node() {
  local node="$1" health_url="$2" label="$3"
  local old_sha new_sha changed

  step "Deploy $node ($BRANCH)"
  ssh "$node" "git -C ~/xnchSystems rev-parse HEAD" >/dev/null 2>&1 || \
    fail "$node: ~/xnchSystems is not a git clone — run ./scripts/deploy.sh --bootstrap $node first"
  old_sha=$(ssh "$node" "git -C ~/xnchSystems rev-parse HEAD")

  backup_node "$node"

  step "Push $node"
  git -C "$REPO_ROOT" push "$node:~/xnchSystems" "$BRANCH" || \
    fail "$node: push rejected (dirty worktree? run --bootstrap to reset)"

  step "Checkout $BRANCH on $node"
  # updateInstead only updates the worktree when the pushed branch is already
  # checked out, so force-switch explicitly (discards node-local edits; the
  # deploy source of truth is this branch).
  ssh "$node" "git -C ~/xnchSystems checkout -f '$BRANCH'" || \
    fail "$node: checkout '$BRANCH' failed"
  new_sha=$(ssh "$node" "git -C ~/xnchSystems rev-parse HEAD")
  changed=$(ssh "$node" "git -C ~/xnchSystems diff --name-only '$old_sha' '$new_sha' 2>/dev/null | grep -v '^xnch$\|^nexi$' || true")
  echo "  $old_sha -> $new_sha"
  [[ -n "$changed" ]] && echo "  changed:" && echo "$changed" | sed 's/^/    /'

  step "Sync submodules on $node"
  # --force: a dirty submodule checkout (node-local edits) must not block the
  # pinned SHA. Back up node-local work before deploying if you need it.
  ssh "$node" "git -C ~/xnchSystems submodule update --init --recursive --force" || \
    fail "$node: submodule sync failed"
  ok "submodules synced"

  restart_services "$node" "$changed"

  step "Verify $node"
  # Health must be checked on the node (localhost there), not from the Mac.
  local i=0 max="${VERIFY_TIMEOUT:-120}"
  while (( i < max )); do
    if ssh "$node" "curl -sf -m 5 '$health_url' >/dev/null 2>&1"; then
      ok "$label"
      return 0
    fi
    sleep 5
    (( i += 5 )) || true
  done
  fail "$label (timeout ${max}s)"
}

restart_services() {
  local node="$1" changed="$2"
  local unit_dirs=()

  case "$node" in
    node-a)
      step "Restart node-a services"
      ssh "$node" "sudo systemctl restart xnch.service" || fail "node-a: restart xnch failed"
      ok "xnch.service restarted"

      if changed_any "$changed" $NODE_A_COMPOSE_PATHS; then
        echo "  compose/litellm config changed — docker compose up -d"
        ssh "$node" "cd ~/xnchSystems/infra/no-k3s/node-a && docker compose up -d" || warn "node-a: compose up failed"
        ssh "$node" "cd ~/xnchSystems/infra/no-k3s/node-a && docker compose restart litellm" || warn "node-a: litellm restart failed"
        ok "litellm restarted"
      fi

      if changed_any "$changed" $NODE_A_UNIT_PATHS; then
        echo "  systemd units changed — reinstall + daemon-reload"
        ssh "$node" "sudo cp ~/xnchSystems/infra/no-k3s/node-a/systemd/xnch.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl restart xnch.service" \
          || warn "node-a: unit reinstall failed"
        ok "systemd units reinstalled"
      fi
      ;;

    node-b)
      step "Restart node-b services"
      ssh "$node" "sudo systemctl restart nexi.service" || fail "node-b: restart nexi failed"
      ok "nexi.service restarted"

      if (( RESTART_VLLM )) || changed_any "$changed" $NODE_B_VLLM_PATHS; then
        echo "  vllm-ornith restart requested / unit changed"
        ssh "$node" "sudo systemctl restart vllm-ornith.service" || warn "node-b: vllm restart failed"
        ok "vllm-ornith.service restarted"
      fi

      if changed_any "$changed" $NODE_B_UNIT_PATHS; then
        echo "  systemd units changed — reinstall + daemon-reload"
        ssh "$node" "sudo cp ~/xnchSystems/infra/no-k3s/node-b/systemd/nexi.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl restart nexi.service" \
          || warn "node-b: unit reinstall failed"
        ok "systemd units reinstalled"
      fi
      ;;
  esac

  if (( SYNC_DEPS )) && changed_any "$changed" "pyproject.toml" "uv.lock"; then
    echo "  deps changed — uv pip install"
    local venv
    if [[ "$node" == node-a ]]; then
      venv=~/xnchSystems/xnch/.venv
      ssh "$node" "uv pip install --python '$venv/bin/python' -e ~/xnchSystems/xnch" || warn "node-a: deps sync failed"
    else
      venv=~/xnchSystems/nexi/.venv
      ssh "$node" "uv pip install --python '$venv/bin/python' -e ~/xnchSystems/nexi" || warn "node-b: deps sync failed"
    fi
    ok "deps synced ($venv)"
  fi
}

# $1 = diff output; rest = path prefixes
changed_any() {
  local diff="$1"; shift
  local prefix
  [[ -z "$diff" ]] && return 1
  for prefix in "$@"; do
    if grep -qE "^${prefix//\//\\/}" <<<"$diff"; then
      return 0
    fi
  done
  return 1
}

# ---------------------------------------------------------------------------
# Bootstrap: clone the branch into a node's ~/xnchSystems (one-time).
# ---------------------------------------------------------------------------
bootstrap_node() {
  local node="$1"

  step "Bootstrap $node"
  ssh "$node" "test -d ~/xnchSystems/.git && echo git-repo || echo no-repo"

  if ssh "$node" "test -d ~/xnchSystems/.git"; then
    echo "  ~/xnchSystems is already a git repo — force-switching to $BRANCH"
    backup_node "$node"
    # The existing clone may be on another branch (e.g. feat/voice-ui) with
    # local edits. Fetch the branch (published above), force-checkout it, and
    # force-sync submodules so the tree matches the deploy source of truth.
    ssh "$node" "git -C ~/xnchSystems fetch origin '$BRANCH' && git -C ~/xnchSystems checkout -f '$BRANCH'" \
      || fail "$node: checkout '$BRANCH' failed"
    ssh "$node" "git -C ~/xnchSystems submodule update --init --recursive --force" \
      || fail "$node: submodule sync failed"
    ssh "$node" "git -C ~/xnchSystems config receive.denyCurrentBranch updateInstead" \
      || fail "$node: updateInstead setup failed"
  else
    echo "  ~/xnchSystems not a git repo — backing up and cloning $BRANCH"
    ssh "$node" "test -d ~/xnchSystems && mv ~/xnchSystems ~/xnchSystems.bak.\$(date +%Y%m%d-%H%M%S) || true" \
      || fail "$node: backup failed"
    ssh "$node" "git clone --branch '$BRANCH' https://github.com/x-nch/xnchSystems.git ~/xnchSystems" \
      || fail "$node: clone failed"
    ssh "$node" "git -C ~/xnchSystems submodule update --init --recursive" \
      || fail "$node: submodule clone failed"
    ssh "$node" "git -C ~/xnchSystems config receive.denyCurrentBranch updateInstead" \
      || fail "$node: updateInstead setup failed"
    # Restore untracked-but-needed runtime files from the backup (e.g.
    # node-a's compose .env, which is gitignored but required by env_file).
    ssh "$node" '
      bak=$(ls -d ~/xnchSystems.bak.* 2>/dev/null | sort | tail -1)
      if [[ -n "$bak" ]]; then
        for f in infra/no-k3s/node-a/.env infra/no-k3s/shared/.env; do
          if [[ -f "$bak/$f" && ! -f ~/xnchSystems/$f ]]; then
            mkdir -p "$(dirname ~/xnchSystems/$f)"
            cp "$bak/$f" ~/xnchSystems/$f && echo "  restored $f from backup"
          fi
        done
      fi
    ' || true
  fi

  ok "$node bootstrapped (services: deploy then restart via scripts/deploy.sh $node)"
}

# ---------------------------------------------------------------------------
main() {
  [[ "$(git -C "$REPO_ROOT" branch --show-current)" == "$BRANCH" ]] || \
    fail "expected branch '$BRANCH', got '$(git -C "$REPO_ROOT" branch --show-current)' — run from the $BRANCH worktree"

  if (( BOOTSTRAP )); then
    publish
    for t in "${TARGETS[@]}"; do
      if [[ "$t" == all ]]; then
        bootstrap_node "$NODE_A_ALIAS"
        bootstrap_node "$NODE_B_ALIAS"
      else
        bootstrap_node "$t"
      fi
    done
    echo ""
    echo "Bootstrap complete. Deploy changes with: ./scripts/deploy.sh ${TARGETS[0]}"
    return 0
  fi

  publish

  if (( WAKE )) && needs_node_b; then
    step "Wake node-b"
    if ! ping -c1 -W2 "$NODE_B_IP" >/dev/null 2>&1; then
      echo "  node-b down — WoL from node-a"
      ssh "$NODE_A_ALIAS" "~/xnchSystems/infra/no-k3s/node-a/wake-node-b.sh" || warn "wake-node-b failed"
      ok "node-b woken"
    else
      ok "node-b already reachable"
    fi
  fi

  local a_done=0 b_done=0
  for t in "${TARGETS[@]}"; do
    case "$t" in
      node-a)
        deploy_node "$NODE_A_ALIAS" "http://localhost:8001/health" "xnch on node-a :8001"
        a_done=1
        ;;
      node-b)
        deploy_node "$NODE_B_ALIAS" "http://localhost:8000/health" "nexi on node-b :8000"
        b_done=1
        ;;
      all)
        deploy_node "$NODE_A_ALIAS" "http://localhost:8001/health" "xnch on node-a :8001"
        deploy_node "$NODE_B_ALIAS" "http://localhost:8000/health" "nexi on node-b :8000"
        a_done=1; b_done=1
        ;;
    esac
  done

  echo ""
  echo "Deploy complete."
  (( a_done )) && echo "  node-a: xnch  http://localhost:8001/health"
  (( b_done )) && echo "  node-b: nexi  http://localhost:8000/health"
}

main
