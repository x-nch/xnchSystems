#!/usr/bin/env bash
# Install node_exporter on a xnch node. No credentials involved.
#   sudo ./install-node-exporter.sh          # Node A (basic collectors)
#   sudo ./install-node-exporter.sh gpu      # Node B (+ systemd lock-holder collector)
set -euo pipefail

NODE_EXPORTER_VERSION="${NODE_EXPORTER_VERSION:-1.8.2}"
UNIT_SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/node_exporter.service"
PROFILE="${1:-control}"

[[ "$(id -u)" -ne 0 ]] && { echo "run with sudo" >&2; exit 1; }

case "$PROFILE" in
  control)
    OPTIONS=""
    ;;
  gpu)
    # Lock-holder signal: expose active state of the units participating in
    # the Ornith <-> Vision Media Stack exclusivity. Adjust the regex if the
    # vision stack unit is named differently on this host.
    OPTIONS="${NODE_EXPORTER_UNIT_INCLUDE:---collector.systemd --collector.systemd.unit-include=\"(vllm-ornith|.*vision.*media.*|nvidia-ready)\\.service\"}"
    ;;
  *) echo "unknown profile: $PROFILE (use: control|gpu)" >&2; exit 1 ;;
esac

echo "=== node_exporter ${NODE_EXPORTER_VERSION} (${PROFILE}) ==="
if [[ ! -x /usr/local/bin/node_exporter ]]; then
  url="https://github.com/prometheus/node_exporter/releases/download/v${NODE_EXPORTER_VERSION}/node_exporter-${NODE_EXPORTER_VERSION}.linux-amd64.tar.gz"
  tmp="$(mktemp -d)"
  curl -fsSL "$url" -o "$tmp/ne.tgz"
  tar -xzf "$tmp/ne.tgz" -C "$tmp"
  install -m 0755 "$tmp/node_exporter-${NODE_EXPORTER_VERSION}.linux-amd64/node_exporter" /usr/local/bin/
  rm -rf "$tmp"
else
  echo "  binary already present, skipping download"
fi

printf 'OPTIONS=%s\n' "$OPTIONS" > /etc/default/node_exporter
install -m 0644 "$UNIT_SRC" /etc/systemd/system/node_exporter.service
systemctl daemon-reload
systemctl enable --now node_exporter.service
systemctl is-active node_exporter.service
curl -sf http://localhost:9100/metrics | head -1 && echo "node_exporter OK on :9100"
