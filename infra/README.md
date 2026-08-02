# XNCH / Nexi Deployment

## Node Labels

Label your nodes before applying manifests:

```bash
kubectl label node i7-node role=memory
kubectl label node i9-node role=inference
```

## Apply Manifests

```bash
# Namespace
kubectl apply -f k8s/namespaces.yaml

# ConfigMaps
kubectl apply -f k8s/configmaps.yaml

# Memory node (i7)
kubectl apply -f k8s/i7-node/

# Inference node (i9)
kubectl apply -f k8s/i9-node/

# CronJobs
kubectl apply -f k8s/jobs/
```

## Verify

```bash
kubectl get all -n xnch-system
kubectl get pods -n xnch-system -o wide
```

## Secrets

Required secrets (create before deploying):

| Secret | Keys |
|--------|------|
| `postgres-secret` | `password` |
| `xnch-secret` | `auth_secret` |
| `litellm-secret` | `master_key` |
| `langfuse-secret` | `nextauth_secret`, `salt` |
| `huggingface-secret` | `token` |

Example:

```bash
kubectl create secret generic postgres-secret -n xnch-system --from-literal=password='<your-pw>'
```

## PVCs

Required PersistentVolumeClaims are created automatically:
- `xnch-data` — xnch server data (SQLite, keys, audit)
- `xnch-vault` — perception vault documents
- `pgdata` — PostgreSQL 50Gi via StatefulSet volumeClaimTemplate
