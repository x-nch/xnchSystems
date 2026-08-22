#!/usr/bin/env bash
# End-to-end smoke test for xnch + nexi + litellm stack.
# Run on Node A (192.168.50.1). Requires operator actor and valid XNCH_AUTH_SECRET.
set -euo pipefail

NODE_A="${NODE_A:-localhost}"
NODE_B="${NODE_B:-192.168.50.2}"
AUTH_SECRET="${XNCH_AUTH_SECRET:-$(grep '^XNCH_AUTH_SECRET=' ~/.xnch/xnch.env | cut -d= -f2)}"
LITELLM_KEY="${LITELLM_MASTER_KEY:-$(grep '^LITELLM_MASTER_KEY=' ~/.xnch/xnch.env 2>/dev/null | cut -d= -f2 || grep '^LITELLM_MASTER_KEY=' ~/xnchSystems/infra/no-k3s/node-a/.env | cut -d= -f2)}"

TOKEN=$(AUTH_SECRET="$AUTH_SECRET" python3 -c "
import jwt, time, os
secret = os.environ['AUTH_SECRET']
print(jwt.encode({'sub': 'operator', 'exp': int(time.time()) + 3600}, secret, algorithm='HS256'))
")

pass() { echo "  OK  $1"; }
fail() { echo "  FAIL $1"; exit 1; }

echo "=== Health ==="
curl -sf "http://${NODE_A}:8001/health" | grep -q '"status":"ok"' && pass "xnch :8001" || fail "xnch :8001"
curl -sf "http://${NODE_B}:8000/health" | grep -q '"status":"ok"' && pass "nexi :8000 (node-b)" || fail "nexi :8000"
curl -sf "http://${NODE_A}:4000/health/liveliness" | grep -qi alive && pass "litellm :4000" || fail "litellm :4000"
curl -sf "http://${NODE_B}:8082/health" >/dev/null && pass "vllm :8082 (node-b)" || fail "vllm :8082"

MODELS=$(curl -sf "http://${NODE_A}:4000/v1/models" -H "Authorization: Bearer ${LITELLM_KEY}")
echo "$MODELS" | grep -q '"ornith"' && pass "litellm model ornith registered" || fail "litellm model ornith missing (try: docker compose restart litellm)"

echo ""
echo "=== Pipeline ==="
SESSION=$(curl -sf -X POST "http://${NODE_A}:8001/session/init" \
  -H "Content-Type: application/json" \
  -d "{\"auth_token\":\"Bearer ${TOKEN}\",\"raw_input\":\"list running services\",\"input_type\":\"TEXT\"}")
echo "$SESSION" | grep -q '"status":"EXECUTING"' && pass "session/init -> nexi pipeline" || fail "session/init: $SESSION"

CHAT=$(curl -sf -X POST "http://${NODE_A}:8001/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TOKEN}" \
  -d '{"model":"ornith","messages":[{"role":"user","content":"what is redis status?"}]}')
echo "$CHAT" | grep -q '"content"' && pass "/v1/chat/completions" || fail "/v1/chat/completions: $CHAT"

NEXI_CHAT=$(curl -sf -X POST "http://${NODE_A}:8001/nexi/chat" \
  -H "Content-Type: application/json" \
  -d '{"session_id":"e2e-smoke","message":"ping","actor_role":"operator"}')
echo "$NEXI_CHAT" | grep -q '"response"' && pass "/nexi/chat (direct LLM)" || fail "/nexi/chat: $NEXI_CHAT"

echo ""
echo "=== Scraper ==="
STORE_RESULT=$(curl -sf -X POST "http://${NODE_A}:8001/mcp/tools/call" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TOKEN}" \
  -d '{"name":"xnch_scraper_store","arguments":{"urls":["https://example.com"],"tier":"static"}}' 2>&1) || true
echo "$STORE_RESULT" | grep -q '"chunks_stored"' && pass "scraper store" || fail "scraper store: $STORE_RESULT"

QUERY_RESULT=$(curl -sf -X POST "http://${NODE_A}:8001/mcp/tools/call" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TOKEN}" \
  -d '{"name":"xnch_scraper_query","arguments":{"query":"example domain","n_results":3}}' 2>&1) || true
echo "$QUERY_RESULT" | grep -q '"results"' && pass "scraper query" || fail "scraper query: $QUERY_RESULT"

echo ""
echo "All end-to-end checks passed."
