# Gateway & Chat APIs

Sources: `xnch/routes/chat.py`, `xnch/routes/nexi_gateway.py`,
`xnch_mcp/chat_tools.py`, `nexi/main.py`.

## On xnch :8001

### `POST /v1/chat/completions`

OpenAI-compatible relay: request is forwarded to LiteLLM
(`LITELLM_BASE_URL`, key `LITELLM_API_KEY`), so any OpenAI-speaking client can
use local models (`model: "qwen3-xml"` public alias → litellm routes to
`ornith-1.0-35b` on Node B). No memory, no tools — pure completion relay.

### `POST /nexi/chat` — the agent surface

Full tool-loop chat:

1. `injection_guard.scan_input`.
2. Context assembly: L1 working turns (20) + L2 semantic recall (top_k 5,
   min score 0.35) + L3 entity connections + sensory tail → system prompt
   (persona + capability summary).
3. Model routing: `classify_request` picks local ornith vs judgment model.
4. LiteLLM chat with tools = native `xnch_*` ∪ bridged `{crg_,am_,doc_}` —
   round cap 3, or 5 while bridge servers are connected
   ([bridge flow](../architecture/mcp-bridge.md#request-flow)).
5. Turns appended to L1; conversation episode written to L2 after guard.

Related reads: `POST /nexi/memory/recall`, `GET /nexi/memory/surface`,
`GET /nexi/system-prompt` (plain text), `GET /nexi/capabilities`,
`GET /nexi/tools`.

### `POST /nexi/chat/stream`

SSE variant of `/nexi/chat`; token stream relayed as events (muse consumes via
the same-origin gateway proxy; proxy sets `maxDuration 300` for long streams).

### Voice: `/nexi/voice/*`

`transcribe` (STT), `speak` / `speak/upload` (piper TTS),
`chat` (audio in → chat → audio out). Caps in [env-vars](env-vars.md#voice).

## On nexi :8000 (service-to-service)

| Endpoint | Purpose |
|---|---|
| `POST /session/start` | pipeline steps 1–10; returns EXECUTING |
| `POST /callback/outcome` | receives outcome from xnch → prediction_delta writeback |
| `GET /health` | liveness |
| `GET /nexi/capabilities` | full capability document |
| `POST /nexi/refresh` | force capability/infra re-probe |

## muse proxy: `/api/gateway/*`

Same-origin Next.js route (`web/src/app/api/gateway/[...path]/route.ts`)
forwarding to `XNCH_GATEWAY_URL` (default home-LAN :8001): strips hop-by-hop
headers, passes SSE through, mints `X-Gateway-Token` for non-GET
`workflows|approvals` paths when `XNCH_GATEWAY_SECRET` set.
Model: [auth reference](auth-model.md#gateway-hybrid-b).
