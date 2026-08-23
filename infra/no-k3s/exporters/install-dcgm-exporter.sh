#!/usr/bin/env bash
# Install DCGM exporter on Node B. Runs the official NVIDIA container via the
# existing docker install; bootstraps nvidia-container-toolkit if missing.
# No credentials involved. Run: sudo ./install-dcgm-exporter.sh
set -euo pipefail

DCGM_IMAGE="${DCGM_IMAGE:-nvcr.io/nvidia/k8s/dcgm-exporter:3.3.5-3.4.1-ubuntu22.04}"
UNIT_SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/dcgm-exporter.service"

[[ "$(id -u)" -ne 0 ]] && { echo "run with sudo" >&2; exit 1; }
command -v docker >/dev/null || { echo "docker required" >&2; exit 1; }
command -v nvidia-smi >/dev/null || { echo "nvidia driver required (run setup-gpu-driver.sh first)" >&2; exit 1; }

echo "=== nvidia-container-toolkit ==="
if ! command -v nvidia-ctk >/dev/null; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y --no-install-recommends nvidia-container-toolkit
  nvidia-ctk runtime configure --runtime=docker
  systemctl restart docker
else
  echo "  already installed"
fi

echo "=== dcgm-exporter (${DCGM_IMAGE}) ==="
install -m 0644 "$UNIT_SRC" /etc/systemd/system/dcgm-exporter.service
systemctl daemon-reload
systemctl enable --now dcgm-exporter.service

echo "waiting for :9400 ..."
for _ in $(seq 1 30); do
  if curl -sf http://localhost:9400/metrics | rg -q "DCGM_FI_DEV_GPU_TEMP"; then
    echo "dcgm-exporter OK on :9400"
    exit 0
  fi
  sleep 2
done
echo "WARN: dcgm-exporter did not expose DCGM metrics within 60s — check: journalctl -u dcgm-exporter" >&2
exit 1
