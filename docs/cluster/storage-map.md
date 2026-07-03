# Storage Map — Live Cluster 2026-06-28

## StorageClass

**Only storage class:** `local-path` (default)
- Provisioner: `rancher.io/local-path`
- Reclaim policy: Delete
- Volume binding mode: `WaitForFirstConsumer`
- Backing: HostPath on node where pod is scheduled
- **All PVs are node-pinned** via `nodeAffinity` (not portable)

## PV/PVC Inventory

| PVC Name | Namespace | PV Name | Size | Access | Pod Mount | Node | Actual Path | Status |
|----------|-----------|---------|------|--------|-----------|------|-------------|--------|
| **xnch-vault** | xnch-system | pvc-7d66f5be-... | 100Gi | RWO | xnch-server | gate7 | local-path-provisioner managed | Bound |
| **xnch-data** | xnch-system | pvc-7da9a1e1-... | 20Gi | RWO | xnch-server | gate7 | local-path-provisioner managed | Bound |
| **pgdata-postgres-pgvector-0** | xnch-system | pvc-8e85b0ec-... | 50Gi | RWO | postgres-pgvector | gate7 | local-path-provisioner managed | Bound |
| **agentmemory-pvc** | xnch-system | pvc-8d65ef27-... | 10Gi | RWO | agentmemory | gate7 | `.../storage/pvc-8d65ef27..._xnch-system_agentmemory-pvc` | Bound/Provisioned |

## Volume Mount Details

### xnch-7577f8df-rhb2b
| Volume Name | Type | Source | Mount Path (inferred) |
|-------------|------|--------|----------------------|
| config | ConfigMap | xnch-config | (config files) |
| data | PVC | xnch-data (20Gi) | /data (likely) |
| kube-api-access | ServiceAccount | token | /var/run/secrets/kubernetes.io |

### postgres-pgvector-0
| Volume Name | Type | Source | Mount Path |
|-------------|------|--------|------------|
| pgdata | PVC | pgdata-postgres-pgvector-0 (50Gi) | `/var/lib/postgresql/data` |
| kube-api-access | ServiceAccount | token | /var/run/secrets/kubernetes.io |

**Disk usage within container:** `/var/lib/postgresql/data` is on `/dev/sda4` (49G total, 17G used, 31G free — 36% used). Note: this is the host partition, the container sees sda4 shared with the host /var partition.

### agentmemory-6fbf5b69f4-kvrjr
| Volume Name | Type | Source | Mount Path (inferred) |
|-------------|------|--------|----------------------|
| agentmemory-storage | PVC | agentmemory-pvc (10Gi) | /data or /app/data |
| kube-api-access | ServiceAccount | token | /var/run/secrets/kubernetes.io |

### litellm-7bc747bb54-xlmrd
| Volume Name | Type | Source | Mount Path (inferred) |
|-------------|------|--------|----------------------|
| config | ConfigMap | litellm-config | (config files) |
| kube-api-access | ServiceAccount | token | /var/run/secrets/kubernetes.io |

### No-PVC Pods (no persistent storage)
- nexi, langfuse, mem0, redis, zep — no PVCs defined
- zep uses a hostPath volume (`/home/x-nch/tiktoken-cache` on xnch-core) for tokenizer cache

## Host Storage Layout

### gate7 (i7-node)
| Mount | Size | Used | Avail | Use% | Purpose |
|-------|------|------|-------|------|---------|
| `/dev/sda3` | 40G | 13G | 26G | 33% | Root OS |
| `/dev/sda4` | 49G | 17G | 31G | 36% | /var (k3s data, PVs) |
| `/dev/sda5` | 826G | 1.7G | 782G | 1% | /home (user data, vault) |
| Total | 915G | 31.7G | 839G | 3.5% | |

### xnch-core (i9-node)
| Mount | Size | Used | Avail | Use% | Purpose |
|-------|------|------|-------|------|---------|
| `/dev/nvme0n1p2` | 49G | 30G | 17G | 65% | Root OS (tight!) |
| `/dev/nvme0n1p3` | 30G | 1.2G | 27G | 4% | /var (k3s agent data) |
| `/dev/nvme0n1p4` | 1.8T | 240G | 1.4T | 15% | /home (user data, model storage) |
| Total | 1.88T | 271G | 1.44T | 14% | |

## Storage Critical Observations

### Node-Pinned (NOT Portable)
**ALL 4 PVs are node-pinned to gate7 via nodeAffinity. If gate7 fails, ALL stateful data is lost:**
- PostgreSQL database (50GB) — Langfuse traces, LiteLLM config, xnch app data
- Vault (100GB) — presume this is unused/empty
- xnch app data (20GB)
- agentmemory data (10GB)

### Reclaim Policy: Delete
- All PVs are reclaim=Delete. If the PVC is deleted, data is destroyed.
- No backup mechanism visible.

### No ReadWriteMany
- All PVs are RWO (ReadWriteOnce), no pod can share a volume across nodes.

### xnch-core Root Disk Pressure
- `/dev/nvme0n1p2` is at 65% (30G used of 49G) — root partition is relatively full.

### Storage Provisioning Logs
From local-path-provisioner logs:
```
Creating volume pvc-8d65ef27... at gate7:/var/lib/rancher/k3s/storage/pvc-8d65ef27..._xnch-system_agentmemory-pvc
```
All PVs are under `/var/lib/rancher/k3s/storage/` on gate7.
