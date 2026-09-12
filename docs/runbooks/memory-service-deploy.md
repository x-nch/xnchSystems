# Memory service deploy (node-a)

## Preconditions
- Phase 2 code merged; `ss -ltn | grep 8003` empty on node-a.
- `XNCH_MEMORY_TOKEN` set in `/home/x-nch/.xnch/xnch.env` (same file the unit reads).
- LangGraph pipeline OFF or accept that it is skipped in remote mode.

## Deploy
1. **Stop the gateway FIRST (Kuzu safety).** The gateway owns the Kuzu file while
   `XNCH_MEMORY_EMBEDDED=true`. If the embedded gateway is still running, the
   memory-service cannot open the same Kuzu file (single-owner invariant). Never
   start the service against a live embedded gateway:
   ```
   sudo systemctl stop xnch
   ```
2. Install the unit:
   ```
   sudo cp infra/no-k3s/node-a/systemd/xnch-memory.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now xnch-memory
   curl -s -H "X-Internal-Token: $XNCH_MEMORY_TOKEN" http://127.0.0.1:8003/healthz
   # {"status":"ok","tiers":{"postgres":true,"kuzu":true}}
   ```
3. Flip the gateway (node-a `~/.xnch/xnch.env`):
   ```
   XNCH_MEMORY_EMBEDDED=false
   XNCH_MEMORY_SERVICE_URL=http://127.0.0.1:8003
   XNCH_MEMORY_TOKEN=<same token>
   ```
   `sudo systemctl restart xnch`
4. Verify: `python -m clients.cli mcp test --skip-chat` (recall + store tools pass);
   web UI graph page streams (`/graph/stream` relay); chat works with recall.
5. Consolidation: confirm the timer's next fire lands in `journalctl -u xnch-memory`
   (POST /v1/consolidation/run, 200).
6. Prometheus: add a scrape job for `192.168.50.1:8003` (the service exposes
   FastAPI metrics via the same middleware pattern the gateway uses — if the
   metrics middleware is not yet wired into `build_app`, wire it the same way
   `xnch/main.py:294-296` does `install_metrics_middleware`, then reload Prometheus).

## Rollback (instant)
- Set `XNCH_MEMORY_EMBEDDED=true` (or remove the line) in `~/.xnch/xnch.env`,
  `sudo systemctl restart xnch`. The gateway reconstructs embedded stores.
- The service can keep running (it owns Kuzu only while the gateway is in remote
  mode; in embedded mode the GATEWAY owns the Kuzu file — stop one before the other:
  when rolling back, stop `xnch-memory` first if both would open the same Kuzu file).

## Invariants
- Exactly ONE process may own the Kuzu file (`~/.xnch/graph.kuzu` or db_path-derived
  location): embedded gateway OR memory-service — never both. The embedded/remote
  switch guarantees this by construction.
- `am_*` tools (agentmemory) are unaffected — this service covers xnch L0-L3 only.