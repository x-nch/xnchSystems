#!/usr/bin/env bash
# Test connected MCP bridge servers through Nexi (gate7 xnch :8001)
# Prefer CLI:  python -m cli mcp test
set -euo pipefail

BASE="${XNCH_BASE_URL:-http://127.0.0.1:8001}"
ACTOR="${XNCH_ACTOR:-nexi}"
SESSION="mcp-test-$(date +%s)"

pass=0
fail=0

run() {
  local name="$1"
  shift
  printf '\n▶ %s\n' "$name"
  if "$@"; then
    echo "  ✓ PASS"
    pass=$((pass + 1))
  else
    echo "  ✗ FAIL"
    fail=$((fail + 1))
  fi
}

mcp_call() {
  local tool="$1"
  local args="${2:-{}}"
  curl -sf -X POST "$BASE/mcp/call" \
    -H "X-Actor-Role: $ACTOR" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"$tool\",\"arguments\":$args}"
}

check_json() {
  python3 -c "$1"
}

echo "XNCH MCP bridge test suite"
echo "  BASE=$BASE  ACTOR=$ACTOR"
echo "================================"

run "xnch health" check_json "
import json,sys,urllib.request
r=json.load(urllib.request.urlopen('$BASE/health'))
assert r.get('status')=='ok', r
print('  status:', r['status'])
"

run "bridge servers (3 connected)" check_json "
import json,sys,urllib.request
req=urllib.request.Request('$BASE/mcp/servers', headers={'X-Actor-Role':'$ACTOR'})
r=json.load(urllib.request.urlopen(req))
connected=[s for s in r['servers'] if s.get('connected')]
print('  connected:', [s['server_id'] for s in connected])
assert len(connected)>=3, connected
"

run "tool count for nexi" check_json "
import json,sys,urllib.request
req=urllib.request.Request('$BASE/mcp/tools', headers={'X-Actor-Role':'$ACTOR'})
r=json.load(urllib.request.urlopen(req))
n=len(r['tools'])
print('  tools:', n)
assert n>=35, n
"

run "native: xnch_health" check_json "
import json,subprocess
out=subprocess.check_output(['curl','-sf','-X','POST','$BASE/mcp/call',
  '-H','X-Actor-Role:$ACTOR','-H','Content-Type: application/json',
  '-d','{\"name\":\"xnch_health\",\"arguments\":{}}'])
r=json.loads(out)['result']
assert r.get('mcp_bridge',{}).get('enabled'), r
print('  mcp_bridge tools:', r['mcp_bridge'].get('tool_count'))
"

run "crg: list_graph_stats" check_json "
import json,subprocess
out=subprocess.check_output(['curl','-sf','-X','POST','$BASE/mcp/call',
  '-H','X-Actor-Role:$ACTOR','-H','Content-Type: application/json',
  '-d','{\"name\":\"crg_list_graph_stats_tool\",\"arguments\":{}}'])
r=json.loads(out)['result']
assert r.get('status')=='ok', r
print('  nodes:', r.get('total_nodes'), 'embeddings:', r.get('embeddings_count'))
"

run "crg: semantic_search McpBridgePool" check_json "
import json,subprocess
out=subprocess.check_output(['curl','-sf','-X','POST','$BASE/mcp/call',
  '-H','X-Actor-Role:$ACTOR','-H','Content-Type: application/json',
  '-d','{\"name\":\"crg_semantic_search_nodes_tool\",\"arguments\":{\"query\":\"McpBridgePool\",\"limit\":3}}'])
r=json.loads(out)['result']
assert r.get('results'), r.get('summary')
print('  ', r.get('summary'))
"

run "crg: callers_of invoke_tool" check_json "
import json,subprocess
out=subprocess.check_output(['curl','-sf','-X','POST','$BASE/mcp/call',
  '-H','X-Actor-Role:$ACTOR','-H','Content-Type: application/json',
  '-d','{\"name\":\"crg_query_graph_tool\",\"arguments\":{\"pattern\":\"callers_of\",\"target\":\"/home/x-nch/xnchSystems/xnch_mcp/registry.py::invoke_tool\"}}'])
r=json.loads(out)['result']
names=[x['name'] for x in r.get('results',[])]
assert 'chat_with_tools' in names, names
print('  callers:', names)
"

run "am: memory_recall" check_json "
import json,subprocess
out=subprocess.check_output(['curl','-sf','-X','POST','$BASE/mcp/call',
  '-H','X-Actor-Role:$ACTOR','-H','Content-Type: application/json',
  '-d','{\"name\":\"am_memory_recall\",\"arguments\":{\"query\":\"MCP bridge\",\"limit\":2}}'])
r=json.loads(out)['result']
assert 'results' in r, r
print('  results:', len(r['results']))
"

run "doc: resolve-library-id FastAPI" check_json "
import json,subprocess
out=subprocess.check_output(['curl','-sf','-X','POST','$BASE/mcp/call',
  '-H','X-Actor-Role:$ACTOR','-H','Content-Type: application/json',
  '-d','{\"name\":\"doc_resolve-library-id\",\"arguments\":{\"libraryName\":\"FastAPI\",\"query\":\"lifespan\"}}'])
r=json.loads(out)['result']
assert r.get('matches'), r
print('  matches:', len(r['matches']))
"

run "doc: query-docs" check_json "
import json,subprocess
out=subprocess.check_output(['curl','-sf','-X','POST','$BASE/mcp/call',
  '-H','X-Actor-Role:$ACTOR','-H','Content-Type: application/json',
  '-d','{\"name\":\"doc_query-docs\",\"arguments\":{\"libraryId\":\"/fastapi/fastapi\",\"query\":\"lifespan\"}}'])
r=json.loads(out)['result']
assert r.get('status')=='ok', r
print('  snippets:', len(r.get('snippets',[])))
"

echo ""
echo "================================"
echo "Live Nexi chat tests (needs LiteLLM + Ornith)"
echo "================================"

run "nexi/chat: doc tool" check_json "
import json,subprocess
out=subprocess.check_output(['curl','-sf','-X','POST','$BASE/nexi/chat',
  '-H','Content-Type: application/json',
  '-d','{\"session_id\":\"$SESSION-doc\",\"message\":\"Use doc_query-docs for /fastapi/fastapi query lifespan. One sentence only.\"}'],
  timeout=120)
r=json.loads(out)
assert r.get('response'), r
print('  ', r['response'][:120])
"

run "nexi/chat: crg tool" check_json "
import json,subprocess
out=subprocess.check_output(['curl','-sf','-X','POST','$BASE/nexi/chat',
  '-H','Content-Type: application/json',
  '-d','{\"session_id\":\"$SESSION-crg\",\"message\":\"Use crg_query_graph_tool callers_of on invoke_tool. List caller names only.\"}'],
  timeout=120)
r=json.loads(out)
assert 'chat_with_tools' in r.get('response','') or 'call_tool' in r.get('response',''), r
print('  ', r['response'][:120])
"

echo ""
echo "================================"
printf "Result: %d passed, %d failed\n" "$pass" "$fail"
[[ "$fail" -eq 0 ]]
