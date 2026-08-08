# Nexi anonymous web search (SearXNG)

Self-hosted metasearch on gate7 — no commercial search API keys.

## Phase 1 — SearXNG infra

```bash
cd /home/x-nch/xnchSystems/infra/no-k3s/node-a
docker compose up -d searxng
curl -s 'http://127.0.0.1:8888/search?q=test&format=json' | head
```

- Binds **127.0.0.1:8888** only (not exposed to LAN)
- Settings: `infra/no-k3s/node-a/searxng/settings.yml`
- JSON format enabled for API access

## Phase 2 — xnch native tool

Policy: `~/.xnch/web-search.yaml` (from `infra/no-k3s/shared/web-search.example.yaml`)

```bash
cp infra/no-k3s/shared/web-search.example.yaml ~/.xnch/web-search.yaml
sudo systemctl restart xnch.service
```

| Tool | Tier | Actors |
|------|------|--------|
| `xnch_web_search` | T0_READ | `nexi`, `operator` |

## Verify

```bash
# CLI
python -m cli mcp call xnch_web_search --arg query="vLLM latest release" --arg limit=3
python -m cli mcp call xnch_health | jq .result.web_search

# curl
curl -s -X POST http://127.0.0.1:8001/mcp/call \
  -H 'X-Actor-Role: nexi' -H 'Content-Type: application/json' \
  -d '{"name":"xnch_web_search","arguments":{"query":"LiteLLM changelog"}}'

# Interactive Nexi
python -m cli chat "What's new in vLLM? Use xnch_web_search — don't guess."
```

## Anonymity properties

- No Brave/Serper/Tavily API keys
- Queries exit via gate7 SearXNG (metasearch), not Nexi directly
- Curated engines: duckduckgo, brave, wikipedia (google/bing disabled in settings)
- **Search only** — no `web_fetch` in v1 (SSRF risk deferred)

## Tool routing

| Need | Tool |
|------|------|
| Current events / CVEs / release notes | `xnch_web_search` |
| Code structure | `crg_*` |
| Offline library snippets | `doc_*` |
| Cross-session memory | `am_*` |
