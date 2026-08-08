#!/usr/bin/env bash
# Wake Node B (xnch-core) via WoL. Run only from Node A (gate7).
set -euo pipefail

NODE_B_IP="${NODE_B_IP:-192.168.50.2}"
WAKE_MAX_WAIT_S="${WAKE_MAX_WAIT_S:-180}"
PING_INTERVAL_S="${PING_INTERVAL_S:-10}"

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

Send a Wake-on-LAN packet to xnch-core (Node B) and wait until it responds to ping.
Must be run from Node A (gate7) where \`wakecore\` is configured.

Options:
  --no-wait       Send WoL only; do not wait for ping
  -h, --help      Show this help
EOF
}

WAIT=1
while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-wait) WAIT=0 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
  esac
  shift
done

command -v wakecore >/dev/null 2>&1 || {
  echo "wakecore not found — install/configure WoL on Node A (gate7)" >&2
  exit 1
}

echo "=== Wake Node B ($NODE_B_IP) ==="
wakecore

if (( ! WAIT )); then
  echo "  OK  WoL sent (not waiting)"
  exit 0
fi

elapsed=0
while (( elapsed < WAKE_MAX_WAIT_S )); do
  if ping -c1 -W2 "$NODE_B_IP" >/dev/null 2>&1; then
    echo "  OK  Node B reachable (${elapsed}s)"
    exit 0
  fi
  sleep "$PING_INTERVAL_S"
  elapsed=$((elapsed + PING_INTERVAL_S))
  echo "  ... waiting for $NODE_B_IP (${elapsed}s)"
done

echo "  FAIL Node B did not respond within ${WAKE_MAX_WAIT_S}s" >&2
exit 1
