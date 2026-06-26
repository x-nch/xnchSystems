## First Boot — Bare Ubuntu → Nexi Responding

From fresh k3s nodes to a working system. Node hostnames must be resolvable via DNS or `/etc/hosts`.

### 1. Label Nodes

```bash
kubectl label node <i7-hostname> role=memory
kubectl label node <i9-hostname> role=inference
```

**Expected:** no errors.

**Failure:** `node "<hostname>" not found` — check `kubectl get nodes`, verify hostname.

### 2. Create Namespace

```bash
kubectl apply -f deploy/k8s/namespaces.yaml
```

**Expected:**
```
namespace/xnch-system created
```

**Failure:** YAML parse error — check indentation. `kubeconfig not set` — check `KUBECONFIG` or `~/.kube/config`.

### 3. Apply i7-Node Manifests

Apply in order. Wait for `rollout status` before proceeding to the next.

```bash
# Database layer
kubectl apply -f deploy/k8s/i7-node/redis.yaml
kubectl rollout status -n xnch-system deploy/redis

kubectl apply -f deploy/k8s/i7-node/postgres-pgvector.yaml
kubectl rollout status -n xnch-system statefulset/postgres-pgvector

# Graph store (not yet wired, but needed for schema)
kubectl apply -f deploy/k8s/i7-node/kuzu.yaml
kubectl rollout status -n xnch-system deploy/kuzu

# Services
kubectl apply -f deploy/k8s/i7-node/litellm-deployment.yaml
kubectl rollout status -n xnch-system deploy/litellm

kubectl apply -f deploy/k8s/i7-node/xnch-deployment.yaml
kubectl rollout status -n xnch-system deploy/xnch

kubectl apply -f deploy/k8s/i7-node/langfuse.yaml
kubectl rollout status -n xnch-system deploy/langfuse

# Perception (GPU, last)
kubectl apply -f deploy/k8s/i7-node/perception-daemonset.yaml
kubectl rollout status -n xnch-system daemonset/perception
```

**Failure at any step:** `rollout status` times out → `kubectl describe pod -n xnch-system <pod>` for events. Common issues: image pull (check registry), nodeSelector mismatched (node lacks `role=memory` label), PVC pending (no storage class).

### 4. Apply i9-Node Manifests

```bash
# Inference (GPU required)
kubectl apply -f deploy/k8s/i9-node/vllm-gemma4.yaml
kubectl rollout status -n xnch-system deploy/vllm-gemma4

# Engine + supporting services
kubectl apply -f deploy/k8s/i9-node/nexi-deployment.yaml
kubectl rollout status -n xnch-system deploy/nexi

kubectl apply -f deploy/k8s/i9-node/mem0-deployment.yaml
kubectl rollout status -n xnch-system deploy/mem0

kubectl apply -f deploy/k8s/i9-node/zep-deployment.yaml
kubectl rollout status -n xnch-system deploy/zep
```

**Failure:** vLLM OOM is most common — `kubectl logs -n xnch-system deploy/vllm-gemma4`. See runbook **gemma4-down.md**.

### 5. Seed Identity Memories

Seeded automatically on xnch startup via `cold_start_seeder.seed_identity_memories()`. It checks `search_memory("episodes", "identity")` and skips if already seeded.

To verify or re-seed manually:

```bash
kubectl exec -n xnch-system deploy/xnch -- python -c "
from nexi.character.cold_start_seeder import seed_identity_memories
from xnch.memory.pg_episodic_store import PgEpisodicStore
import asyncio
store = PgEpisodicStore('postgresql://xnch:\$POSTGRES_PASSWORD@postgres-pgvector:5432/xnch')
asyncio.run(seed_identity_memories(store))
"
```

**Expected:**
```
Seeded 7 identity facts (or 0 if already present)
```

**Failure:** DB not reachable — check postgres-pgvector is `Running`. Redis not reachable — check redis pod.

### 6. Verify All Pods

```bash
kubectl get pods -A
```

**Expected (all `Running` or `Completed`):**
```
NAMESPACE      NAME                              READY   STATUS    RESTARTS
xnch-system    redis-xxxxx                       1/1     Running   0
xnch-system    postgres-pgvector-0               1/1     Running   0
xnch-system    kuzu-xxxxx                        1/1     Running   0
xnch-system    litellm-xxxxx                     1/1     Running   0
xnch-system    xnch-xxxxx                        1/1     Running   0
xnch-system    langfuse-xxxxx                    1/1     Running   0
xnch-system    perception-xxxxx                  1/1     Running   0
xnch-system    vllm-gemma4-xxxxx                 1/1     Running   0
xnch-system    nexi-xxxxx                        1/1     Running   0
xnch-system    mem0-xxxxx                        1/1     Running   0
xnch-system    zep-xxxxx                         1/1     Running   0
```

Any `CrashLoopBackOff` or `Pending` → `kubectl describe pod -n xnch-system <name>`.

### 7. Verify Nexi Persona Endpoint

```bash
kubectl exec -n xnch-system deploy/xnch -- curl -s http://xnch:8001/nexi/system-prompt
```

Or externally:
```bash
curl http://i7-node:8001/nexi/system-prompt
```

**Expected:** Returns Nexi persona as plaintext — starts with `You are Nexi...`, includes identity and communication style from `nexi_character.yaml`.

**Failure:** `connection refused` → xnch not running. `404` → route not registered (check `nexi_gateway.py`).

### 8. End-to-End Smoke Test

```bash
# From the i9 node or a machine with openclaw installed
bash deploy/openclaw/start_nexi.sh
```

Also test the chat endpoint directly:
```bash
curl -X POST http://i7-node:8001/nexi/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"smoke-test-1","message":"hello","actor_role":"openclaw"}'
```

**Expected:** Nexi responds. If streaming, `chat/stream` returns SSE events.

**Failure:**
- `400 {"detail":"Input rejected by injection guard"}` — message triggered a pattern. Try different message.
- `502 LiteLLM unavailable` — LiteLLM not proxying to vLLM. Check `kubectl logs -n xnch-system deploy/litellm`.

---

**All 8 steps verified. System is operational.**
