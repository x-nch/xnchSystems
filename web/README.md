# muse — xnchSystems web app

Next.js UI for the xnch control plane: HITL **approvals queue**, **workflow
builder**, plus chat, memory, graph, system and tools views. Talks to xnch
exclusively through a same-origin proxy route — no CORS, SSE-safe.

Operating context: [`docs/architecture/workflows-hitl.md`](../docs/architecture/workflows-hitl.md) ·
[`docs/guides/operate-hitl.md`](../docs/guides/operate-hitl.md).

## Run (on this Mac)

```bash
npm install
npm run dev        # development server on :3000
# or for daily use:
npm run build && npm run start
```

Port 3000 is free here — Langfuse's :3000 lives on gate7, not on the Mac.

## Configuration

| Env var | Purpose |
|---|---|
| `XNCH_GATEWAY_URL` | upstream xnch gateway; default `http://192.168.1.10:8001` (gate7 home-LAN) |
| `XNCH_GATEWAY_SECRET` | shared HMAC secret; must match xnch's `XNCH_GATEWAY_SECRET`. Set on both sides or `/workflows`+`/approvals` writes are rejected/open depending on server config |

## Gateway proxy (`src/app/api/gateway/[...path]/route.ts`)

- Forwards to `<XNCH_GATEWAY_URL>/<path>` stripping hop-by-hop headers;
  search params preserved; SSE streams pass through. (`maxDuration 300` is a
  serverless-host knob — inert when self-hosted on the Mac.)
- **Hybrid-B**: non-GET requests under `workflows/` or `approvals/` get a fresh
  `X-Gateway-Token` minted from the secret — the browser never sees it.
  Token format: `<expiry_epoch>.<hmac_sha256(secret, expiry)>`, TTL 300 s.

## Layout

```
src/app/            routes: chat · memory · graph · network · system · tools · workflows
                    api/gateway/[...path]/   same-origin proxy
src/components/     approvals/ workflows/ chat/ memory/ graph/ system/ tools/
src/lib/            api clients · approvals · workflows · auth · stores
```

Design language: dark-minimalist chartreuse system per the immutable spec
[`docs/superpowers/specs/2026-08-22-xnchsystems-hitl-dark-minimalist-design.md`](../docs/superpowers/specs/2026-08-22-xnchsystems-hitl-dark-minimalist-design.md).

> Next.js version note: this tree pins a newer Next.js with breaking changes vs
> older conventions — consult `node_modules/next/dist/docs/` before writing code.
