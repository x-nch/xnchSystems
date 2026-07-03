# Live Cluster Inventory — 2026-06-28

## Node Summary

| Node | Role | IP | CPU | RAM | GPU | OS | K8s Ver | Uptime |
|------|------|----|-----|-----|-----|----|---------|--------|
| **gate7** | control-plane, memory | 192.168.1.11 | i7-9750H (6C/12T) | 15Gi | GTX 1650 (no driver) | Ubuntu 24.04.4, 6.17.0-29 | v1.36.2+k3s1 | 5h24m |
| **xnch-core** | inference | 192.168.50.2 | i9-14900K (24C/32T) | 46Gi | RTX 3090 24GiB | Ubuntu 24.04.4, 6.8.0-107 | v1.36.2+k3s1 | 5h18m |

**Notes:**
- gate7 runs k3s server (control-plane); xnch-core runs k3s agent
- gate7 has NVIDIA GTX 1650 but no NVIDIA driver installed — nvidia-smi fails, GPU not usable
- xnch-core has RTX 3090 with driver 590.48.01, CUDA 13.1 — actively running llama-server

---

## Pod Inventory — xnch-system

| Pod | Node | Image | Status | Restarts | CPU Req/Limit | Mem Req/Limit | CPU Actual | Mem Actual | Pod IP |
|-----|------|-------|--------|----------|---------------|---------------|------------|------------|--------|
| **agentmemory-6fbf5b69f4-kvrjr** | gate7 | `node:20-slim` | Running | 0 | 500m/1 | 1Gi/2Gi | 7m | 122Mi | 10.42.0.49 |
| **langfuse-d9f58f9ff-tsfcq** | gate7 | `langfuse/langfuse:2` | Running | 0 | 500m/1 | 768Mi/1536Mi | 1m | 54Mi | 10.42.0.43 |
| **litellm-7bc747bb54-xlmrd** | gate7 | `ghcr.io/berriai/litellm:main-latest` | Running | 0 | 500m/1 | 1Gi/2Gi | 3m | 1018Mi | 10.42.0.44 |
| **postgres-pgvector-0** | gate7 | `pgvector/pgvector:pg16` | Running | 0 | 1/2 | 2Gi/5Gi | 1m | 51Mi | 10.42.0.31 |
| **redis-5c66476f45-td2cz** | gate7 | `redis:7-alpine` | Running | 0 | 250m/500m | 512Mi/1Gi | 14m | 13Mi | 10.42.0.29 |
| **xnch-7577f8df-rhb2b** | gate7 | `xnch/xnch-server:latest` | Running | 0 | 500m/1 | 768Mi/1536Mi | 3m | 123Mi | 10.42.0.33 |
| **mem0-6c9947c9c5-bxmw4** | xnch-core | `mem0/mem0-api-server:latest` | Running | 0 | 250m/500m | 256Mi/512Mi | 18m | 26Mi | 10.42.1.40 |
| **nexi-54466b7668-pz2s6** | xnch-core | `xnch/nexi-engine:latest` | Running | 0 | 1/2 | 1Gi/2Gi | 2m | 81Mi | 10.42.1.63 |
| **zep-6f49ffcd8c-nr66q** | xnch-core | `ghcr.io/getzep/zep:latest` | CrashLoopBackOff | 15 | 500m/1 | 512Mi/1Gi | N/A | N/A | 10.42.1.49 |

## Pod Inventory — kube-system

| Pod | Node | Image | Status | Restarts | CPU Req/Limit | Mem Req/Limit | CPU Actual | Mem Actual | Pod IP |
|-----|------|-------|--------|----------|---------------|---------------|------------|------------|--------|
| **coredns-5f5694d56b-7l8pk** | gate7 | `rancher/mirrored-coredns-coredns:1.14.4` | Running | 0 | 100m/— | 70Mi/170Mi | 5m | 16Mi | 10.42.0.4 |
| **local-path-provisioner-58d557dc48-9nd9h** | gate7 | `rancher/local-path-provisioner:v0.0.36` | Running | 0 | —/— | —/— | 1m | 9Mi | 10.42.0.5 |
| **metrics-server-7c86f97b8d-x2vdw** | gate7 | `rancher/mirrored-metrics-server:v0.8.1` | Running | 0 | 100m/— | 70Mi/— | 11m | 24Mi | 10.42.0.6 |
| **traefik-6cd8c7cd89-2nkdf** | gate7 | `rancher/mirrored-library-traefik:3.7.4` | Running | 0 | —/— | —/— | 1m | 21Mi | 10.42.0.8 |
| **svclb-traefik-59d4599d-8rd2b** | gate7 | `rancher/klipper-lb:v0.4.17` (2 containers) | Running | 0 | —/— | —/— | 0m | 0Mi | 10.42.0.7 |
| **svclb-traefik-59d4599d-wjbdn** | xnch-core | `rancher/klipper-lb:v0.4.17` (2 containers) | Running | 0 | —/— | —/— | 0m | 0Mi | 10.42.0.2 |
| **nvidia-device-plugin-daemonset-sqzdg** | gate7 | `nvcr.io/nvidia/k8s-device-plugin:v0.14.0` | Running | 0 | —/— | —/— | 1m | 3Mi | 10.42.0.16 |
| **nvidia-device-plugin-daemonset-4996b** | xnch-core | `nvcr.io/nvidia/k8s-device-plugin:v0.14.0` | Running | 0 | —/— | —/— | 1m | 20Mi | 10.42.1.10 |

## Orphaned Pods — default

| Pod | Node | Image | Status | Restarts |
|-----|------|-------|--------|----------|
| **test-dns** | xnch-core | `busybox:1.28` | Failed (exit 1) | 0 |
| **dns-final** | xnch-core | `busybox:1.36` | Failed (exit 1) | 0 |

**Notes:**
- All images use `:latest` or mutable tags — no SHA-pinned images (violates quality gate)
- No deployments have liveness/readiness probes configured
- No deployments have PodDisruptionBudgets
- No NetworkPolicies are defined in any namespace
- containerPort is defined for all containers except local-path-provisioner, nvidia-device-plugin, svclb
- All pods run as root (no securityContext with runAsNonRoot)
