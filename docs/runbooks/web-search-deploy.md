# Nexi Anonymous Web Search — Gate7 Deploy Runbook

Deployment and operations for **SearXNG** (self-hosted metasearch on gate7,
`127.0.0.1:8888`) and the native **`xnch_web_search`** tool. No commercial
search API keys.

- Architecture deep-dive: [Nexi MCP Bridge — Architecture Guide](../guides/mcp-bridge.md) (Session 1)
- API reference: [`docs/reference/mcp-http-api.md`](../reference/mcp-http-api.md)
- CLI reference: [`docs/guides/mcp-cli.md`](../guides/mcp-cli.md)
- Chat prompts: [`docs/guides/nexi-test-prompts.md`](../guides/nexi-test-prompts.md)

---

## Live state (checked 2026-08-08)

- SearXNG container: `searxng` **Up (healthy)**, `127.0.0.1:8888->8080/tcp`
- `~/.xnch/web-search.yaml` present
- `xnch_web_search` exposed to `nexi` as `[T0_READ]`
- `xnch_health` reports `web_search.enabled: true`, backend `searxng`

---

## 1. Start SearXNG

```bash
cd /home/x-nch/xnchSystems/infra/no-k3s/node-a
docker compose up -d searxng
docker ps --filter name=searxng
```

**Expected:**

```
searxng   Up ... (healthy)   127.0.0.1:8888->8080/tcp
```

- Binds **`127.0.0.1:8888` only** (host port) — not exposed to the LAN.
- Settings: `infra/no-k3s/node-a/searxng/settings.yml`, mounted into the
  container at `/etc/searxng`.
- `SEARXNG_BASE_URL=http://127.0.0.1:8888/` set in compose.
- JSON output is enabled (`search.formats: [html, json]`) — required for the
  `xnch_web_search` tool.

**Failure:** container not healthy → `docker logs searxng`. Common cause:
`settings.yml` secret_key placeholder (`xnch-change-me-...`) is fine locally,
but if the instance name/locale syntax is off, SearXNG refuses to start.

Smoke-test SearXNG directly (JSON API):

```bash
curl -s 'http://127.0.0.1:8888/search?q=test&format=json' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('results:', len(d.get('results', [])))"
```

**Expected:** `results: N` (engines return up to the limit; live example returned
20).

---

## 2. Copy the web-search policy

```bash
cp infra/no-k3s/shared/web-search.example.yaml ~/.xnch/web-search.yaml
```

Config keys (`web-search.example.yaml`): `backend: searxng`,
`searxng_url: http://127.0.0.1:8888`, `max_results: 5`, `max_results_cap: 10`,
`timeout_s: 15`, `safesearch: 1`, engines `[duckduckgo, brave, wikipedia]`,
`allowed_actors: [nexi, operator]`.

**Expected:**

```bash
ls -l ~/.xnch/web-search.yaml
# -rw------- 1 x-nch x-nch ... /home/x-nch/.xnch/web-search.yaml
```

---

## 3. Restart xnch

```bash
sudo systemctl restart xnch.service
systemctl is-active xnch.service
```

**Expected:** `active`. Confirm the tool is live:

```bash
cd /home/x-nch/xnchSystems
/home/x-nch/xnchSystems/xnch/.venv/bin/python -m cli mcp tools --actor nexi --prefix xnch_web_search
# actor: nexi  tools: 1
#   xnch_web_search  [T0_READ]
```

---

## 4. Smoke tests

**CLI:**

```bash
cd /home/x-nch/xnchSystems
/home/x-nch/xnchSystems/xnch/.venv/bin/python -m cli mcp call xnch_web_search \
  --arg query="vLLM latest release" --arg limit=3

# CLI unwraps /mcp/call result, so web_search sits at the top level:
/home/x-nch/xnchSystems/xnch/.venv/bin/python -m cli mcp call xnch_health \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('web_search'))"
```

**Expected:**

- The search call returns `status: ok`, `backend: searxng`. `result_count` may be
  `0` — the curated engines can return nothing for a given query (see
  [Troubleshooting](#troubleshooting)); `status: ok` means the pipeline is healthy.
- `web_search` from `xnch_health` shows `enabled: true`, backend `searxng`,
  `engines: [duckduckgo, brave, wikipedia]`, `allowed_actors: [nexi, operator]`.

(For the raw endpoint, the result is nested: `curl ... /mcp/call | jq '.result.web_search'`.)

**curl:**

```bash
curl -s -X POST http://127.0.0.1:8001/mcp/call \
  -H 'X-Actor-Role: nexi' -H 'Content-Type: application/json' \
  -d '{"name":"xnch_web_search","arguments":{"query":"LiteLLM changelog"}}'
```

**Interactive Nexi:**

```bash
cd /home/x-nch/xnchSystems
/home/x-nch/xnchSystems/xnch/.venv/bin/python -m cli chat \
  "What's new in vLLM? Use xnch_web_search — don't guess."
```

The `web_search_health` and `xnch_web_search` cases of
`python -m cli mcp test --skip-chat` also cover this.

---

## Anonymity properties

- **No API keys** — no Brave/Serper/Tavily credentials anywhere in the stack.
- **Queries exit via SearXNG** (metasearch on gate7), not from the Nexi runtime
  directly; the container is bound to loopback and is not exposed to the LAN.
- **Curated engines** — `duckduckgo`, `brave`, `wikipedia`; google/bing are
  disabled in `searxng/settings.yml`.
- **Safe search on** — `safesearch: 1` in both the SearXNG settings and the
  web-search policy.
- **Search only in v1** — there is **no `web_fetch`** tool. Fetching/SSRF risk
  is deliberately deferred; `xnch_web_search` returns titles, snippets, and URLs
  only.

---

## Tool routing

| Need | Tool |
|------|------|
| Current events / CVEs / release notes | `xnch_web_search` |
| Code structure / callers / tests / impact | `crg_*` |
| Offline library snippets (FastAPI, Pydantic, MCP, LiteLLM, Kuzu) | `doc_*` |
| Cross-session memory / lessons / actions | `am_*` |

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `xnch_web_search` fails: `Connection refused` to `127.0.0.1:8888` | SearXNG container not running | `docker compose up -d searxng`; `docker ps`; restart xnch |
| `searxng` container unhealthy | Settings parse error or dependency failure | `docker logs searxng`; fix `infra/no-k3s/node-a/searxng/settings.yml`; `docker compose restart searxng` |
| `xnch_health` shows `web_search: null` or `enabled: false` | `~/.xnch/web-search.yaml` missing or not restarted after adding | `cp` the example, `sudo systemctl restart xnch`, re-check |
| Tool call returns `{"error": true, ...}` with HTTP 4xx/5xx from SearXNG | SearXNG rate-limited or an engine returned an error | Retry; check `docker logs searxng`; SearXNG is a single-node instance — keep `max_results` low (5) to avoid hammering upstream engines |
| No results for a query while an unfiltered search returns hits | Curated engines (duckduckgo/brave/wikipedia) returned nothing for that query — live on 2026-08-08 the curated list often returns `result_count: 0` (google/bing are disabled by design, and DDG/Brave can be rate-limited upstream) | The tool still returns `status: ok` — do **not** treat `result_count: 0` as an outage. Verify engine health directly: `curl -s 'http://127.0.0.1:8888/search?q=test&format=json&engines=duckduckgo,brave,wikipedia'`; check `docker logs searxng`. Adding an engine means changing both `~/.xnch/web-search.yaml` `engines:` and `searxng/settings.yml`, then restarting xnch |
| Unexpected engine appears in results | `engines:` list in policy and `settings.yml` out of sync | Align `~/.xnch/web-search.yaml` engines with `searxng/settings.yml`; restart xnch |

---

## See also

- [Memory routing deploy runbook](memory-routing-deploy.md) — episodic vs agentmemory
- [MCP bridge deploy runbook](mcp-bridge-deploy.md) — bridge servers, CRG graph, verification
- [Nexi MCP Bridge — Architecture Guide](../guides/mcp-bridge.md)
- [MCP CLI reference](../guides/mcp-cli.md)
- [Nexi test prompts](../guides/nexi-test-prompts.md)
- API reference: [`docs/reference/mcp-http-api.md`](../reference/mcp-http-api.md)
- Source notes: `misc/notes/nexi-web-search.md`
