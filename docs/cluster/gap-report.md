# Gap Report — Plan vs Reality

## Critical Failures

| # | Issue | Severity | Details |
|---|-------|----------|---------|
| **C1** | **zep in CrashLoopBackOff** | CRITICAL | Failed: `store.type must be set`. Zep requires store type configuration (postgres or memory). No `.env` file, no config passed. Has restarted 15 times. |
| **C2** | **Nexi endpoint unresponsive** | CRITICAL | POST `/nexi/chat` timed out after 30s. Cannot verify end-to-end request flow. Possible causes: (a) missing route, (b) hanging on zep dependency, (c) wrong URL path. |
| **C3** | **GTX 1650 on gate7 unusable** | CRITICAL | nvidia-smi: "NVIDIA-SMI has failed because it couldn't communicate with the NVIDIA driver." The nvidia-device-plugin on gate7 runs but is non-functional. |
| **C4** | **No resource limits on system pods** | HIGH | traefik, local-path-provisioner, nvidia-device-plugin, svclb all have no resource requests/limits. Could be starved or OOM-killed under pressure. |
| **C5** | **No health probes anywhere** | HIGH | Zero deployments have liveness or readiness probes defined. Kubernetes cannot detect or recover from hung pods. |
| **C6** | **All images use `:latest`** | HIGH | Every user image (`xnch/xnch-server:latest`, `xnch/nexi-engine:latest`, `mem0/mem0-api-server:latest`, `litellm:main-latest`, `zep:latest`) uses mutable tags. No SHA pinning. Rollbacks are unreliable. |
| **C7** | **No PodDisruptionBudgets** | MEDIUM | Zero PDBs defined. Voluntary disruptions (node drain, updates) will kill all replicas. |
| **C8** | **Single replica everything** | MEDIUM | Every deployment runs exactly 1 replica. No HA, no rolling update tolerance. |
| **C9** | **Storage not portable** | MEDIUM | All 4 PVs node-pinned to gate7. If gate7 fails, ALL data (PostgreSQL, agentmemory, xnch data, vault) is lost. |
| **C10** | **No NetworkPolicies** | MEDIUM | Any pod can reach any other pod. No isolation between namespaces. |

## Missing Components

| Component | Expected | Reality | Impact |
|-----------|----------|---------|--------|
| **Perception service** | Perception agent on gate7 | **Not found** — no pods, no deployments with "perception" in name | Missing sensing capability |
| **Kuzu graph database** | Graph store for nexi | **Not found** — no kuzu files in nexi container | May affect AI reasoning capabilities |
| **Ingress routes** | Traffic routing via Traefik | **Not defined** — Traefik runs but has no Ingress resources | Can only reach services via NodePort IPs |
| **Vault (100Gi PVC)** | Encrypted secrets storage | **Exists but empty/unused** — PVC provisioned but likely no data written | 100Gi allocated unnecessarily |
| **Consolidation cronjob** | Nightly data consolidation | **Never run** — lastScheduleTime is null, age 5h | First run not triggered yet |
| **HPAs** | Autoscaling definitions | **Not defined** — all deployments fixed at 1 replica | No elasticity |
| **Backup mechanism** | PVC/pod backups | **Not found** — no backup jobs, volumesnapshot classes, or tools | All data at risk |
| **GPU in K8s** | RTX 3090 managed by K8s | **Runs on host as systemd service** — not under K8s control | No scheduling, health-checking, or scaling |

## Degraded Services

| Service | Status | Degradation |
|---------|--------|-------------|
| **zep** | CrashLoopBackOff (15 restarts) | Memory service unavailable |
| **vllm-gemma4** | Running (host) | Not managed by K8s; manual failover if process dies |
| **Nexi** | Running but unresponsive to test | End-to-end flow broken |
| **agentmemory** | Running (new, 13m old) | First version had BackOff restart — fixed in second revision |

## Unexpected Resources

| Resource | Reason for Presence |
|----------|-------------------|
| **test-dns, dns-final** (default ns, Failed) | Orphaned dns debugging pods |
| **dns-check** (default ns, Running) | Pod from THIS review session |
| **agentmemory revision history** | 2 revisions in 15 minutes — image config thrashing |
| **langfuse revision history** | 12 revisions — excessive rolling updates during setup |
| **nexi revision history** | 5 revisions in 5 hours |
| **gemma4-llama service** | systemd service on xnch-core, NOT in K8s |

## Production Readiness Recommendations

### Immediate (Crime Scene)
1. **Configure zep** — pass `ZEP_STORE_TYPE=postgres` env var and connection string to fix CrashLoopBackOff
2. **Fix nexi endpoint** — investigate why `/nexi/chat` times out; check routes and dependencies
3. **Remove nvidia-device-plugin from gate7** or install nvidia driver on gate7

### Short-term (This Week)
4. **Add liveness/readiness probes** to every deployment — start with simple TCP probes
5. **Pin images by SHA** — `docker pull` then resolve to digest for all 10+ container images
6. **Add PodDisruptionBudgets** — `minAvailable: 1` for all xnch-system deployments
7. **Define Ingress routes** for xnch, nexi, litellm, langfuse through Traefik
8. **Define NetworkPolicies** — at minimum default-deny-ingress per namespace
9. **Add resource limits to kube-system pods** — traefik, local-path-provisioner, etc.
10. **Set up nodeSelector properly** — all xnch-system pods have it, but ensure it's accurate

### Medium-term
11. **Add GPU node to K8s scheduling** — move llama-server into a K8s pod with nvidia-container-runtime
12. **Implement PVC backup** — velero or k8up for automated PostgreSQL snapshots
13. **Increase replica counts** — 2 minimum for xnch, nexi, litellm, langfuse
14. **Define HPAs** — based on CPU at minimum
15. **Reduce langfuse PVC to appropriate size** — 50Gi for postgres may be excessive (currently using <1Gi)
16. **Remove unused 100Gi vault PVC** or use it
17. **Clean up orphaned pods** — test-dns, dns-final
18. **Run consolidation cronjob manually** to verify it works
19. **Add securityContext** — runAsNonRoot, allowPrivilegeEscalation: false, drop ALL capabilities
20. **Replace `:latest` tags with CI-pinned SHA tags**

### Architectural Concerns
- **No HA** — single control-plane (gate7), single replicas, single storage node
- **Manual GPU management** — llama-server outside K8s is a single point of failure
- **No backup/DR** — 50Gi PostgreSQL database with no backup strategy
- **No monitoring/alerting** — no prometheus, grafana, or alertmanager
- **All eggs in one storage basket** — all PVs on gate7's local disk
