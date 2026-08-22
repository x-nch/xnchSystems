# xnchSystems — auth headers & tokens

Auth is per-surface. There is no single SSO; each component verifies its own
credential.

## 1. Control-plane client auth (Mac → xnch :8001)

The CLI (`cli/client.py`) builds an `Authorization` header:

1. **`XNCH_AUTH_TOKEN` set** → used verbatim; a bare token gets a `"Bearer "`
   prefix. (`export XNCH_AUTH_TOKEN="Bearer <jwt>"` — this is how
   `xnch-cli auth token` output is consumed.)
2. **`XNCH_AUTH_SECRET` set** → mints an **HS256 JWT**:
   ```
   payload = { sub: <actor>, iss: "xnch", exp: now + 3600 }
   header   = Authorization: Bearer <jwt>
   ```
   Actor comes from `XNCH_ACTOR` (default `operator`).
3. **neither** → dev fallback literal `actor:<actor_id>`.

The server (`xnch/auth/`) accepts either `Bearer <hs256-jwt>` (verified with
`XNCH_AUTH_SECRET`) or `actor:<actor_id>`. Roles seen in the wild:
`operator`, `nexi` (used by `/mcp/*`).

```bash
# Mac client bootstrap (scripts/setup-mac-voice-client.sh writes this):
export XNCH_BASE_URL=http://192.168.1.10:8001
export XNCH_ACTOR=operator
export XNCH_AUTH_SECRET=<shared secret from gate7 ~/.xnch/xnch.env>
```

## 2. Where the token goes

| Surface | Where credential lives |
|---------|------------------------|
| Most xnch routes | `Authorization: Bearer <jwt>` header |
| `/session/init` | JSON body field `auth_token` |
| `/mcp/*` | `X-Actor-Role` header (role, not token) + optional `X-Trace-Id`, `X-Session-Id` |
| `/nexi/chat`, `/nexi/voice/chat` | Body field `actor_role` (default `operator`) |
| `/v1/chat/completions` | `Authorization: Bearer <jwt>` (required) |
| nexi → xnch calls | `Bearer <jwt>` minted by nexi with its `NEXI_*` secret (same `XNCH_AUTH_SECRET`-style HS256) — TODO: confirm exact env in `~/.xnch/nexi.env` |

## 3. Execution tokens (RS256)

- `/verdict` issues an **execution token** (RS256, `TokenSigner` in
  `xnch/auth/token.py`) authorizing a downstream action; `nexi` verifies it
  against the public key fetched from `GET /auth/public-key`
  (`{algorithm: "RS256", public_key_pem}`).
- TTL by trust level (`_TOKEN_TTL_BY_TRUST`):

  | Trust | TTL |
  |-------|-----|
  | `SYSTEM` | 7 days |
  | `OWNER` | 1 day |
  | `TRUSTED_AGENT` | 1 hour |
  | `EXTERNAL_AGENT` | 30 minutes |
  | `UNTRUSTED` | 0 (invalid) |

- `jti` replay protection; `ExecutionTokenClaims` carries the claims set.
- `/execution/execute` consumes the token; `/execution/outcome` returns
  `execution_token_ref` in the request body.

## 4. Node B sidecars — `X-Internal-Token`

`fs-read-agent` (:8003) and `exec-agent` (:8004) verify a single shared
secret passed in the **`X-Internal-Token`** header (settings
`fs_agent_token` / `exec_agent_token`; env `XNCH_FS_AGENT_TOKEN`,
`XNCH_EXEC_AGENT_TOKEN`). Every route except `/health` requires it; a
mismatch returns 401. They are invoked by xnch MCP tools, not directly from
the Mac.

## 5. media-gateway — Bearer static token

All `/media/*` routes on Node B :8090 require `Authorization: Bearer
<MEDIA_GATEWAY_TOKEN>`. When the token env is unset the gateway fails closed
(503 `gateway token not configured`). Bootstrap: `scripts/media-node-b-agent.sh`
pulls the token from Node B `~/.xnch/media.env` and writes a local
`~/.xnch/node-b.env`/`MEDIA_GATEWAY_TOKEN` for e2e (`infra/no-k3s/media-e2e.sh`).

## 6. LiteLLM

- Admin/API key env: `LITELLM_MASTER_KEY`, `LITELLM_API_KEY` (consumed by
  `infra/no-k3s/e2e-test.sh` for `GET /v1/models`, and by
  `xnch/routes/nexi_gateway.py` via `LITELLM_BASE_URL` + key).
- vLLM backends are keyed with `xnch-vllm-key` per `litellm_config.yaml`.

## Secret handling notes

- Default dev secret is `dev-secret-change-in-production` (`xnch/config.py`);
  production gate7 uses `XNCH_AUTH_SECRET` from `~/.xnch/xnch.env`.
- Never store secrets in the repo — the bootstrap scripts read them from
  `~/.xnch/*.env` (see `scripts/media-node-b-agent.sh`, `scripts/setup-mac-voice-client.sh`).
