# Vercel web UI → gate7 xnch — tunnel deploy

Expose **xnch `:8001`** on gate7 (node-a) to the public internet **without a
home public IP**, so the Next.js app on Vercel (`x-nch.com`) can proxy API
calls through `/api/gateway`.

**Architecture:**

```
Browser → x-nch.com (Vercel) → /api/gateway → https://api.x-nch.com (tunnel) → gate7 :8001
```

The browser never talks to the LAN directly. Vercel server-side routes forward
auth headers (`Authorization`, `X-Actor-Role`) to xnch.

---

## Choose a provider

| Provider | Public URL | Best when |
|----------|------------|-----------|
| **Cloudflare Tunnel** (recommended) | `https://api.x-nch.com` | `x-nch.com` DNS is on Cloudflare |
| **Tailscale Funnel** | `https://<gate7>.<tailnet>.ts.net` | Already on Tailscale, skip Cloudflare |

Both use an **outbound agent on gate7** — no router port-forward.

---

## Prerequisites (gate7)

```bash
systemctl is-active xnch.service
curl -sf http://127.0.0.1:8001/health
```

Repo checkout at `/home/x-nch/xnchSystems` (or set `REPO_ROOT`).

---

## Option A — Cloudflare Tunnel

### A1. Install (gate7)

```bash
cd ~/xnchSystems
chmod +x infra/no-k3s/node-a/setup-vercel-tunnel.sh
./infra/no-k3s/node-a/setup-vercel-tunnel.sh cloudflare
```

Follow the printed steps:

```bash
cloudflared tunnel login
cloudflared tunnel create xnch-gate7
# Edit ~/.cloudflared/config.yml — set credentials-file UUID from create output
cloudflared tunnel route dns xnch-gate7 api.x-nch.com

sudo cp infra/no-k3s/node-a/systemd/cloudflared-xnch.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now cloudflared-xnch.service
```

Config template: `infra/no-k3s/node-a/cloudflared/config.yml.example`

### A2. Verify (any machine)

```bash
curl -sf https://api.x-nch.com/health
```

### A3. Cloudflare Access (strongly recommended)

xnch exposes MCP tools, exec, and filesystem — do not leave the tunnel open.

1. Cloudflare Zero Trust → Access → Applications → add `api.x-nch.com`
2. Policy: allow your email, or create a **Service Token** for Vercel only
3. On Vercel, set env vars (see below) including `CF_ACCESS_CLIENT_ID` /
   `CF_ACCESS_CLIENT_SECRET` so the Next.js proxy can pass the token

---

## Option B — Tailscale Funnel

### B1. Install and enable (gate7)

```bash
cd ~/xnchSystems
./infra/no-k3s/node-a/setup-vercel-tunnel.sh tailscale
```

If not yet on the tailnet:

```bash
sudo tailscale up
./infra/no-k3s/node-a/setup-vercel-tunnel.sh tailscale
```

Persist across reboot:

```bash
sudo cp infra/no-k3s/node-a/systemd/tailscale-funnel-xnch.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now tailscale-funnel-xnch.service
```

### B2. Get public URL

```bash
tailscale funnel status
# e.g. https://gate7.tail1234.ts.net
curl -sf https://gate7.tail1234.ts.net/health
```

Tailnet ACL must allow Funnel for the gate7 node.

---

## Vercel configuration

Project root: **`web/`** (set in Vercel project settings).

| Variable | Example | Required |
|----------|---------|----------|
| `XNCH_GATEWAY_URL` | `https://api.x-nch.com` | Yes |
| `CF_ACCESS_CLIENT_ID` | from Cloudflare service token | If using CF Access |
| `CF_ACCESS_CLIENT_SECRET` | from Cloudflare service token | If using CF Access |

Redeploy after changing env vars.

Local dev (unchanged):

```bash
cd web
XNCH_GATEWAY_URL=http://192.168.1.10:8001 npm run dev
```

### Web UI auth

Operators configure identity in **Settings**:

- **JWT mode** + `XNCH_AUTH_SECRET` (same value as gate7 `~/.xnch/xnch.env`)
- Or paste a short-lived bearer token

xnch enforces auth regardless of tunnel provider.

---

## Streaming / timeouts

Chat and graph views use SSE through `/api/gateway`. Vercel serverless functions
have duration limits (Hobby 10s, Pro up to 300s). The gateway route sets
`maxDuration = 300` (Pro). If streams truncate on Hobby, upgrade plan or
self-host the web UI behind the same tunnel.

---

## Troubleshooting

| Symptom | Check |
|---------|--------|
| Vercel 502 “Cannot reach xnch gateway” | `XNCH_GATEWAY_URL` set? `curl` tunnel URL `/health` from outside LAN |
| CF Access 403 from Vercel | Service token env vars on Vercel; token allowed on `api.x-nch.com` app |
| Tunnel up, xnch down | `systemctl status xnch` on gate7 |
| Tailscale Funnel 404 | `tailscale serve status` / `tailscale funnel status` |
| Auth 401/403 on API | Web Settings → JWT secret matches gate7 `XNCH_AUTH_SECRET` |

**Logs (gate7):**

```bash
journalctl -u cloudflared-xnch -f
journalctl -u tailscale-funnel-xnch -f
journalctl -u xnch -f
```

---

## Related

- Web gateway proxy: `web/src/app/api/gateway/[...path]/route.ts`
- xnch systemd: `infra/no-k3s/node-a/systemd/xnch.service`
- MCP bridge: [mcp-bridge-deploy.md](mcp-bridge-deploy.md)
