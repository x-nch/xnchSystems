# Deployment & Infrastructure Audit — 2026-08-22

**Scope:** no-k3s bare-metal migration (Node A `192.168.50.1` control plane, Node B `192.168.50.2` inference/nexi), path-flattening verification, systemd dependency audit, k8s-parity gaps, secrets hygiene, workstream status.
**Method:** every finding below was verified against file content in this repo this session (paths + line numbers cited). No live systems were touched; no changes applied beyond this report (per operating constraint: report-and-stop on security-sensitive items).
**Reviewer evidence base:** `infra/no-k3s/**`, `infra/k8s/**`, `infra/openclaw/**`, `scripts/deploy.sh`, both submodules @ `3593184` (xnch) / `6f321ee` (nexi), parent @ `04d9356`.

---

## TL;DR — Top findings

| # | Severity | Finding |
|---|----------|---------|
| S1 | **CRITICAL** | Live-looking secrets committed to git in two files (`infra/k8s/secrets-create.sh`, `infra/openclaw/claude-code-agentmemory.env`). The LiteLLM master key appears in **both**, cross-confirming it is a real credential. |
| S2 | HIGH | No unattended boot ordering across nodes: Node B units start after `network.target` only; nexi's lifespan performs **no connectivity checks**, so Node B boots "healthy" with Node A down → silent failure mode. |
| S3 | HIGH | vLLM (`:8082`) serves **unauthenticated** on `0.0.0.0` (unit sets no `--api-key`; the key in litellm config is decorative). Same for nexi `:8000`, fs-read `:8003`, exec-agent `:8004`. Exec-agent is a governed-command surface bound to the LAN. |
| S4 | MEDIUM | Zero resource limits anywhere (no systemd `MemoryMax/CPUQuota`, no compose `mem_limit/cpus`) and no log-rotation config for compose containers (json-file default is unbounded). |
| S5 | MEDIUM | Path flattening is clean in all *code/config/CI* surfaces; residuals remain only in `infra/no-k3s/MIGRATION.md` (active doc) and historical `misc/` records. |
| S6 | LOW/MED | The canonical **14-workstream / 420-hour estimate document is not committed to this repo** — status below is reconstructed from verifiable artifacts. Commit the plan to make wave tracking auditable. |
| S7 | LOW | Stale config details from pre-migration era: `NEXTAUTH_URL=http://192.168.1.10:3000` (wrong subnet), openclaw unit still wired to `k3s.service`, legacy `infra/k8s/` tree retained. |

---

## 1. Path-flattening verification (`xnch/xnch` → `xnch/`)

**Verdict: complete in all executable/config surfaces. Residuals are documentation-only.**

Checked and CLEAN:

| Surface | Evidence |
|---|---|
| Disk layout | `xnch/` and `nexi/` contain code directly at submodule root (`main.py`, `config.py`, …). No nested `xnch/xnch/` or `nexi/nexi/` directories exist. |
| systemd units (all 10) | All use flattened paths: e.g. `WorkingDirectory=/home/x-nch/xnchSystems`, `PYTHONPATH=…/xnchSystems/nexi:…/xnchSystems/xnch` (`node-b/systemd/nexi.service:8-11`). |
| Dockerfiles | `infra/docker/nexi.Dockerfile`: `COPY nexi/ /app/nexi/`, `COPY xnch/ /app/xnch/` ✓; `xnch.Dockerfile` same pattern ✓. |
| Deploy scripts | `scripts/deploy.sh` uses `infra/no-k3s/...` paths throughout (lines 35-39, 242-268). |
| CI configs | None exist anywhere (parent `.github/` has no workflows; neither submodule has `.github/workflows`). Vacuously clean — but see gap G7: there is no CI at all. |

Residual stale references (report-only):

- **Active doc:** `infra/no-k3s/MIGRATION.md:34` → "nexi/nexi/config.py", `:45` → "xnch/xnch/config.py" (Required Code Changes section). Also `MIGRATION.md:244` rollback references `deploy/k8s/` which today lives at `infra/k8s/`.
- **Historical only (acceptable, `misc/` = records):** `misc/QA_REPORT.md`, `misc/report.md`, `misc/MIGRATION_PLAN.md`, `misc/session-ses_0f29.md` use pre-flattening paths.
- Not issues (false-positive classes): `~/.xnch/xnch.env` is an env-file naming convention, not nesting; `xnch/xnch-server:latest` in legacy `infra/k8s/*.yaml` is a container image tag.

## 2. K8s-parity audit (what k3s used to provide)

| Capability | k8s gave | Current state | Gap |
|---|---|---|---|
| Process supervision | restartPolicy + rescheduling | systemd `Restart=on-failure` + `RestartSec=10-15` on every unit; compose `restart: unless-stopped` on all 6 containers | Minor: `on-failure` won't restart a hung-but-alive process; no `WatchdogSec` anywhere |
| Liveness/readiness | probes auto-restart wedged pods | Compose healthchecks present for litellm/langfuse/redis/postgres-pgvector/langfuse-postgres/searxng (`docker-compose.yml:19-130`) ✓. Host services have **no** health gating: `Type=simple` treats "process exists" as healthy; readiness enforced only inside manual `start-node-*.sh` via `wait_http` | **Gap G1:** nothing re-checks health post-boot; a degraded service stays "active". Note `xnch /health` returns HTTP 200 `"degraded"` when Redis is unreachable (`xnch/main.py:211-217`) and `wait_http` only checks status codes — degraded counts as up in boot scripts |
| Resource limits | requests/limits per pod | **None**: no `MemoryMax`/`CPUQuota`/`TasksMax` in any unit; no `mem_limit`/`cpus`/`pids_limit` in compose | **Gap G2:** one noisy service (e.g. vLLM at `gpu-memory-utilization 0.95`, or Langfuse) can starve co-tenants on Node A |
| Log rotation | kubelet/containerd rotation | systemd services → journald (host defaults govern; no override in repo). Compose containers → json-file driver with **no logging options** → unbounded unless host `daemon.json` is configured (not in repo) | **Gap G3:** Langfuse/vLLM-class log volume can fill disk silently |
| Secrets management | k8s Secrets | Plain env files outside repo (`~/.xnch/*.env`) — correct location, but see §5: old secrets leaked into git | Gap covered by S1 |
| Scheduled jobs | CronJob | systemd timers: `consolidation.timer` daily 02:00, `Persistent=true` ✓ | OK (better than k3s here) |
| Service discovery | CoreDNS | Static IPs documented (`.env.example`, MIGRATION.md) | OK by design |
| Boot self-healing | node scheduling | Manual orchestration scripts + WoL (`wake-node-b.sh`) | See §3 |

## 3. Systemd dependencies & boot/restart order (Node A ↔ Node B)

**Verdict: intra-node ordering is partially defined; cross-node ordering exists ONLY when humans run the start scripts. Unattended reboot has silent-failure modes.**

Unit-by-unit:

| Unit | After/Wants | Assessment |
|---|---|---|
| node-a `xnch.service` | `network.target docker.service` (Wants=docker) | Wants ≠ Requires, and docker daemon start ≠ containers healthy. At cold boot xnch races postgres/redis → crash-retry loop until compose containers pass healthcheck. Converges, but noisily and unordered. |
| node-a `consolidation.{service,timer}` | timer: `After=xnch.service` + `Wants=xnch.service`, `DefaultDependencies=no` (USB `/var` workaround), `Persistent=true` | Correctly ordered ✓ |
| node-a `tailscale-funnel-xnch.service` | `Requires=tailscaled xnch` | Correct ✓ (funnel follows xnch) |
| node-a `perception.service`, `vault-indexer.service` | — | **Must stay disabled**: reference non-existent entrypoints (`vision_encoder` server, `index_vault()`); explicitly deferred in MIGRATION.md:113-122 |
| node-b `vllm-ornith.service` | `After=nvidia-ready.service` + `ConditionPathExists=/usr/bin/nvidia-smi` | Good GPU gating ✓ — but `nvidia-ready.service` is generated out-of-band by `setup-gpu-driver.sh:97-116`, not tracked as a unit file in the repo (drift risk) |
| node-b `nexi.service`, `fs-read-agent.service`, `exec-agent.service` | `After=network.target` **only** | **No dependency on local vllm-ornith, none possible cross-node.** |

Cross-node reality check:

- Ordering that exists is **manual**: `start-node-b.sh:75-81` waits for Node A `xnch:8001` + `litellm:4000` before starting units; `start-node-a.sh --wait-node-b` waits for vLLM. Neither runs at boot — enabled units start independently of these scripts.
- **Silent failure confirmed at code level:** nexi's lifespan (`nexi/main.py:95-125`) constructs clients without any connectivity probe, then serves. If Node B reboots while Node A is down (or before Postgres/Redis/LiteLLM are ready), nexi reports its own health as OK while every pipeline call fails downstream. `Restart=on-failure` never triggers because nexi doesn't crash.
- Recommended fixes (not applied): add `ExecStartPre=` readiness curls to node-b units (cheap, effective), and/or a small `nexi-ready` gate; consider `Requires=`+`After=` on `vllm-ornith` for nexi; add `MemoryMax` etc. per §2.

## 4. Workstream status vs. the 14-workstream / 420h estimate

**The estimate document itself is not in the repo.** Searched `docs/`, `misc/`, `scripts/`, session notes and agent memory: the only workstream artifacts present are (a) `misc/Agent_mapping.plan` (a different, earlier **7-workstream** QA-fix mapping), (b) `misc/report.md` (its execution log), (c) `misc/QA_REPORT.md` (issue list A/B/M), and (d) `infra/no-k3s/MIGRATION.md` deployment state. The table below therefore maps the production-readiness scope to **verifiable evidence** and marks statuses accordingly; row numbering is ours, keyed to the artifacts above.

| # | Workstream (reconstructed scope) | Status | Evidence |
|---|---|---|---|
| 1 | Infra migration k3s → bare metal (compose + units + deploy tooling) | **done** | `infra/no-k3s/` complete stack; `MIGRATION.md` phases checked off; `scripts/deploy.sh` automates rollout |
| 2 | Node B inference stack (vLLM Ornith + GPU bootstrap) | **done** | `vllm-ornith.service`, `setup-gpu-driver.sh`, `start-node-b.sh`; MIGRATION notes dated Aug 2026 describe live tuning (`--quantization gptq_marlin`, FLASH_ATTN) |
| 3 | Core QA bugfixes B1–B7 | **done** | `misc/report.md` Phase 0 summary: 7/7 fixed, 192 tests passing; corroborated by git history (e.g. STALE_SESSION retry, outcome payload fix `499649d`) |
| 4 | API surface (OpenAI-compat chat, clarify re-entry) | **done** | `report.md` Phase 2 (B1, A1 fixed); exercised live in `infra/no-k3s/e2e-test.sh:36-45` |
| 5 | Memory/storage unification (canonical store) | **done (v0)** | `report.md` Phase 1: M1 decision (SQLite canonical), M4 removed; deferred siblings M5/M7 tracked separately |
| 6 | Context assembler wiring (rich context into live pipeline, A2) | **blocked** (explicitly deferred) | `report.md` "Deferred": A2 not wired; QA_REPORT.md:43 documents it built-but-disconnected |
| 7 | Orphaned memory services (mem0/zep) decommission | **done** (decommissioned; never integrated) | MIGRATION.md checklist "confirmed decommissioned"; configs retained under `infra/mem0/`, `infra/zep/` |
| 8 | Execution runner (real dispatch target) | **in-progress** | Graceful-fail shipped (`report.md` B4-service: logs+continues); actual runner service still absent (WS7 in Agent_mapping.plan) |
| 9 | Perception service (voice+vision, :8002) | **not-started** | MIGRATION.md:113-117: "no HTTP server entrypoint exists"; unit kept but must remain disabled |
| 10 | Vault indexer | **not-started** | MIGRATION.md:118-119: calls nonexistent `index_vault()`; unit disabled |
| 11 | HITL governance pipeline | **done** (recent) | xnch git: `d440606` tier graph + interrupts, `3593184` `/governance/pipeline` API; parent bumped `e9c7d05` |
| 12 | Goals subsystem (store, CRUD, driver loop, eval harness) | **done** (recent) | xnch: `a92aea5`…`6e8a7bc` goal store/CRUD/simulated execution; nexi: `5788f6e`→`f37f4b7` models/planner/driver, `6f321ee` eval harness |
| 13 | Observability (Langfuse tracing) | **in-progress** | langfuse v2 pinned + healthchecked in compose; PYTHONPATH wiring noted (MIGRATION.md:177-178). Defect: `NEXTAUTH_URL=http://192.168.1.10:3000` is a stale pre-migration IP (`docker-compose.yml:34`) |
| 14 | Security hardening (secrets hygiene, authn on exposed ports, CI gates) | **blocked** | Findings S1/S3/G7: live secrets in git, unauthenticated LAN-exposed services, zero CI in any repo. Needs rotation + remediation plan before P0 can close |

**Wave-sequencing validity:** the shipped set (rows 3-5, 11, 12 + full infra migration) means the early waves' engineering scope is largely overtaken by events. What remains genuinely P0 is concentrated in rows 14 (security), 8 (runner), 13 (observability defect), plus the ops gaps in §2 (G1-G3). Rows 9-10 should be formally re-scoped or dropped rather than carried as open hours. Recommendation: re-baseline the 420h estimate against this table and commit it to the repo so future audits can diff against the plan.

## 5. Secrets & credentials handling

**Verdict: runtime secret placement is correct; repository hygiene has critical violations.**

CRITICAL (rotate + purge from history; report-and-stop observed):

1. `infra/k8s/secrets-create.sh:7-15` — literal values committed: postgres password `e369ee62…`, xnch auth_secret `52b31c9d…`, Langfuse nextauth_secret + salt, LiteLLM master_key `df4d178833bb37cac13628dcf2ce970e5d98e298f1c53eed8baadfe8e505b91d`.
2. `infra/openclaw/claude-code-agentmemory.env:2-3` — tracked in git with real values: `AGENTMEMORY_SECRET=8244db55…`, `LITELLM_API_KEY=df4d1788…` — **identical to the LiteLLM master key above**, confirming both are live credentials. This file slipped past `.gitignore` because it matches neither `.env` nor `.env.*` (needs a `*.env` pattern).

Related exposure (same theme):

3. `litellm-config/config.yaml:6` ships `api_key: xnch-vllm-key`, but `vllm-ornith.service` passes no `--api-key` → vLLM accepts any key; effectively **unauthenticated OpenAI-compatible endpoint on 0.0.0.0:8082**, LAN-wide. Same bind pattern for nexi :8000, fs-read :8003, exec-agent :8004 (the latter executes commands — highest-value target).
4. searxng `secret_key` is a placeholder string (`settings.yml:13`) — mitigated by `127.0.0.1`-only bind (`docker-compose.yml:118`).

Positive controls verified:

- Runtime env lives outside the repo (`~/.xnch/xnch.env`, `~/.xnch/nexi.env` via `EnvironmentFile=`) ✓
- `shared/.env.example` uses only placeholders (`change-me-in-production`) ✓
- `git ls-files` confirms only `.env.example` + the offending agentmemory.env are tracked ✓
- openclaw/mac/zep configs correctly use `api_key_env:` indirection, not literals ✓

## 6. Additional gaps noted (low severity)

- **G7 — No CI anywhere** (parent + both submodules): path-flattening class regressions and secret scanning currently have no automated guard.
- Legacy `infra/k8s/` tree retained (incl. stale `vllm-gemma4.yaml` model name); `openclaw/i7-systemd.service:3-5` still declares `After/Wants=k3s.service`, and MIGRATION.md says k3s remains for system pods on Node A — if the "fully off k3s" premise is now true, these need cleanup.
- Dual env-file conventions: compose reads `node-a/.env`, systemd units read `~/.xnch/*.env`; `e2e-test.sh:9` falls back to the compose one. Document or unify.
- `MIGRATION.md` File Manifest (lines 269-288) is outdated vs. the actual tree (missing agents, scripts, searxng).
- `perception.service`/`vault-indexer.service` ship broken `ExecStart`s in-repo; safe only because they're not installed — add a comment banner in the units themselves to prevent accidental enablement.

## 7. Recommended remediation order

1. Rotate every credential in §5 items 1-2; purge via history rewrite or accept exposure and rotate-only (constraint: operator decision).
2. Add `--api-key` to vLLM + auth on fs/exec agents, or firewall them to Node A only.
3. Add `*.env` to `.gitignore`; move remaining literals to env indirection.
4. `ExecStartPre` readiness gates on node-b units; fix `NEXTAUTH_URL` to `http://192.168.50.1:3000`.
5. Compose `logging: options: max-size/max-file`; systemd `MemoryMax/CPUQuota` for top offenders.
6. Fix MIGRATION.md residual paths; commit the (re-baselined) workstream plan.
