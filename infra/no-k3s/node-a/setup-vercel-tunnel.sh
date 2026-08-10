#!/usr/bin/env bash
# Install and configure an outbound tunnel from gate7 (node-a) so Vercel can
# reach xnch :8001 without a public IP or router port-forward.
#
# Run on gate7 (192.168.50.1 / 192.168.1.10) as x-nch:
#   ./infra/no-k3s/node-a/setup-vercel-tunnel.sh cloudflare
#   ./infra/no-k3s/node-a/setup-vercel-tunnel.sh tailscale
#
# After setup, set on Vercel (web project):
#   XNCH_GATEWAY_URL=https://api.x-nch.com          # cloudflare
#   XNCH_GATEWAY_URL=https://<machine>.<tailnet>.ts.net  # tailscale funnel
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${REPO_ROOT:-$HOME/xnchSystems}"
PROVIDER="${1:-}"

usage() {
  cat <<EOF
Usage: $(basename "$0") <cloudflare|tailscale>

Providers:
  cloudflare   Cloudflare Tunnel → api.x-nch.com (recommended; needs x-nch.com on Cloudflare DNS)
  tailscale    Tailscale Funnel → https://<host>.<tailnet>.ts.net (no Cloudflare account)

Prereqs:
  - xnch.service active on :8001
  - curl http://127.0.0.1:8001/health returns 200

See docs/runbooks/vercel-tunnel-deploy.md for Vercel env vars and Cloudflare Access.
EOF
}

require_xnch() {
  if ! curl -sf http://127.0.0.1:8001/health >/dev/null; then
    echo "error: xnch is not healthy on :8001 — start it first (systemctl status xnch)" >&2
    exit 1
  fi
  echo "ok: xnch /health"
}

install_cloudflared() {
  if command -v cloudflared >/dev/null 2>&1; then
    echo "ok: cloudflared $(cloudflared --version 2>&1 | head -1)"
    return
  fi
  echo "Installing cloudflared…"
  if [[ -f /etc/debian_version ]]; then
  curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | sudo tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null
  echo "deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared $(. /etc/os-release && echo "$VERSION_CODENAME") main" \
    | sudo tee /etc/apt/sources.list.d/cloudflared.list >/dev/null
  sudo apt-get update -qq
  sudo apt-get install -y cloudflared
  else
    echo "error: install cloudflared manually — https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/" >&2
    exit 1
  fi
}

setup_cloudflare() {
  install_cloudflared
  require_xnch

  mkdir -p "$HOME/.cloudflared"
  if [[ ! -f "$HOME/.cloudflared/config.yml" ]]; then
    cp "$SCRIPT_DIR/cloudflared/config.yml.example" "$HOME/.cloudflared/config.yml"
    echo "Wrote ~/.cloudflared/config.yml from example — edit <TUNNEL-UUID> before starting the service."
  fi

  cat <<EOF

Cloudflare Tunnel — manual steps (browser login required once):

  1. cloudflared tunnel login
  2. cloudflared tunnel create xnch-gate7
  3. Edit ~/.cloudflared/config.yml — set credentials-file to the new UUID json
  4. cloudflared tunnel route dns xnch-gate7 api.x-nch.com
  5. Install systemd unit:
       sudo cp "$SCRIPT_DIR/systemd/cloudflared-xnch.service" /etc/systemd/system/
       sudo systemctl daemon-reload
       sudo systemctl enable --now cloudflared-xnch.service
  6. Verify: curl -sf https://api.x-nch.com/health

Vercel → Project → Environment Variables:
  XNCH_GATEWAY_URL=https://api.x-nch.com

Optional (recommended): Cloudflare Access on api.x-nch.com + service token on Vercel:
  CF_ACCESS_CLIENT_ID=...
  CF_ACCESS_CLIENT_SECRET=...

EOF
}

install_tailscale() {
  if command -v tailscale >/dev/null 2>&1; then
    echo "ok: $(tailscale version 2>&1 | head -1)"
    return
  fi
  echo "Installing tailscale…"
  if [[ -f /etc/debian_version ]]; then
    curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/$(. /etc/os-release && echo "$VERSION_CODENAME").noarmor.gpg \
      | sudo tee /usr/share/keyrings/tailscale-archive-keyring.gpg >/dev/null
    curl -fsSL "https://pkgs.tailscale.com/stable/ubuntu/$(. /etc/os-release && echo "$VERSION_CODENAME").tailscale-keyring.list" \
      | sudo tee /etc/apt/sources.list.d/tailscale.list >/dev/null
    sudo apt-get update -qq
    sudo apt-get install -y tailscale
  else
    echo "error: install tailscale manually — https://tailscale.com/download/linux" >&2
    exit 1
  fi
}

setup_tailscale() {
  install_tailscale
  require_xnch

  if ! sudo tailscale status >/dev/null 2>&1; then
    echo "Join tailnet (one-time): sudo tailscale up"
    echo "Then re-run: $0 tailscale"
    exit 0
  fi

  sudo tailscale serve --bg --https=443 http://127.0.0.1:8001
  sudo tailscale funnel --bg 443 on

  PUBLIC_URL="$(tailscale funnel status 2>/dev/null | grep -Eo 'https://[^ ]+' | head -1 || true)"
  if [[ -z "$PUBLIC_URL" ]]; then
    HOST="$(tailscale status --json 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('Self',{}).get('DNSName','').rstrip('.'))" 2>/dev/null || true)"
    PUBLIC_URL="https://${HOST}"
  fi

  cat <<EOF

Tailscale Funnel is active.

Public URL (set on Vercel):
  XNCH_GATEWAY_URL=${PUBLIC_URL}

Verify:
  curl -sf "${PUBLIC_URL}/health"

Persist across reboot:
  sudo cp "$SCRIPT_DIR/systemd/tailscale-funnel-xnch.service" /etc/systemd/system/
  sudo systemctl daemon-reload
  sudo systemctl enable --now tailscale-funnel-xnch.service

Note: Funnel requires HTTPS certificates from Tailscale; ACL must allow funnel on your tailnet.
EOF
}

case "${PROVIDER}" in
  cloudflare|cf) setup_cloudflare ;;
  tailscale|ts) setup_tailscale ;;
  -h|--help|"") usage; exit "${PROVIDER:+0}" 1 ;;
  *) echo "unknown provider: $PROVIDER" >&2; usage; exit 1 ;;
esac
