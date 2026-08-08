#!/usr/bin/env bash
# Permanent NVIDIA driver fix for Node B (xnch-core).
#
# Problem: linux-image-generic can upgrade to a kernel revision before Ubuntu
# publishes matching linux-modules-nvidia-* packages (e.g. 6.8.0-136 gap).
# After a reboot the GPU is invisible and vLLM cannot start.
#
# Fix: use DKMS (nvidia-dkms-590-open) so modules are built for every
# installed kernel. Keep the 590 driver line pinned; block accidental 595
# upgrades that apt may pull via the generic meta-package.
#
# Run once on Node B (requires sudo):
#   ~/xnchSystems/infra/no-k3s/node-b/setup-gpu-driver.sh
#   sudo reboot
#   sudo systemctl enable --now vllm-ornith.service
set -euo pipefail

DRIVER_SERIES="${NVIDIA_DRIVER_SERIES:-590}"
DRIVER_FLAVOUR="${NVIDIA_DRIVER_FLAVOUR:-open}"  # open | (empty for proprietary)

step() { echo ""; echo "=== $1 ==="; }
ok()   { echo "  OK  $1"; }
fail() { echo "  FAIL $1" >&2; exit 1; }

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Re-run with sudo: sudo $0" >&2
  exit 1
fi

dkms_pkg="nvidia-dkms-${DRIVER_SERIES}-${DRIVER_FLAVOUR}"
driver_pkg="nvidia-driver-${DRIVER_SERIES}-${DRIVER_FLAVOUR}"

step "Preflight"
command -v apt-get >/dev/null || fail "apt-get required"
[[ -f /proc/cpuinfo ]] || fail "not on Linux"
ok "running as root on $(hostname)"

step "Install DKMS toolchain + NVIDIA DKMS driver (${DRIVER_SERIES}-${DRIVER_FLAVOUR})"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y --no-install-recommends \
  dkms \
  "linux-headers-$(uname -r)" \
  "$dkms_pkg"

step "Pin driver series (block accidental major-version jumps)"
install -d /etc/apt/preferences.d
install -m 0644 /dev/stdin "/etc/apt/preferences.d/xnch-nvidia-${DRIVER_SERIES}.pref" <<PREF
# Keep NVIDIA driver on the ${DRIVER_SERIES} series for vLLM stability.
Package: nvidia-*-595*
Pin: release *
Pin-Priority: -1

Package: linux-modules-nvidia-595*
Pin: release *
Pin-Priority: -1

Package: nvidia-dkms-${DRIVER_SERIES}-${DRIVER_FLAVOUR} nvidia-driver-${DRIVER_SERIES}-${DRIVER_FLAVOUR}
Pin: release *
Pin-Priority: 1001
PREF
# Prevent apt from swapping 590 -> 595 via meta-package upgrades.
for pkg in nvidia-driver-595 nvidia-driver-595-open nvidia-dkms-595 nvidia-dkms-595-open \
           linux-modules-nvidia-595-open-generic; do
  if apt-cache show "$pkg" &>/dev/null; then
    apt-mark hold "$pkg" 2>/dev/null || true
  fi
done
apt-mark unhold "$driver_pkg" "$dkms_pkg" 2>/dev/null || true
ok "driver ${DRIVER_SERIES} pinned; 595 packages held"

step "Build / load NVIDIA module for $(uname -r)"
dkms autoinstall -k "$(uname -r)" || fail "DKMS build failed for $(uname -r)"
modprobe nvidia || fail "modprobe nvidia failed"
ok "nvidia module loaded"

step "Verify GPU"
if ! nvidia-smi --query-gpu=name,driver_version --format=csv,noheader; then
  fail "nvidia-smi failed after DKMS install — reboot may be required"
fi

step "Install boot-time GPU readiness check"
install -m 0755 /dev/stdin /usr/local/bin/xnch-nvidia-ready.sh <<'SCRIPT'
#!/usr/bin/env bash
set -euo pipefail
MAX_WAIT="${XNCH_NVIDIA_READY_TIMEOUT:-120}"
for ((i = 0; i < MAX_WAIT; i += 2)); do
  if nvidia-smi --query-gpu=name --format=csv,noheader &>/dev/null; then
    exit 0
  fi
  sleep 2
done
echo "xnch-nvidia-ready: GPU not available after ${MAX_WAIT}s" >&2
exit 1
SCRIPT

install -m 0644 /dev/stdin /etc/systemd/system/nvidia-ready.service <<'UNIT'
[Unit]
Description=Wait for NVIDIA GPU driver after boot
DefaultDependencies=no
After=local-fs.target systemd-modules-load.service
Before=vllm-ornith.service
ConditionPathExists=/usr/bin/nvidia-smi

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/local/bin/xnch-nvidia-ready.sh

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable nvidia-ready.service
ok "nvidia-ready.service enabled"

step "Install apt hook — rebuild DKMS modules after kernel package changes"
install -d /etc/apt/apt.conf.d
install -m 0644 /dev/stdin /etc/apt/apt.conf.d/90-xnch-nvidia-dkms <<'APT'
# Rebuild NVIDIA DKMS modules whenever a new kernel image is installed.
DPkg::Post-Invoke {
  "if command -v dkms >/dev/null 2>&1; then dkms autoinstall; fi";
};
APT
ok "apt post-invoke hook installed"

step "Enable vLLM service"
if [[ -f /etc/systemd/system/vllm-ornith.service ]]; then
  systemctl enable vllm-ornith.service
  ok "vllm-ornith.service enabled"
else
  echo "  WARN vllm-ornith.service not installed — copy from infra/no-k3s/node-b/systemd/ first"
fi

echo ""
echo "GPU driver setup complete."
echo "If nvidia-smi worked above, start vLLM: sudo systemctl start vllm-ornith.service"
echo "After future kernel upgrades, DKMS rebuilds automatically; reboot when prompted."
echo "Verify: nvidia-smi && curl -sf http://localhost:8082/health"
