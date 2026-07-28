## Gemma4 Down — vLLM Not Responding

### Detection

- LiteLLM falls back to `claude-judgment` for all requests
- Langfuse traces show `claude-judgment` instead of `gemma4-local`
- Nexi responses are slower (Claude API latency vs local inference)
- `/v1/models` returns empty or errors

### Check

```bash
kubectl logs -n xnch-system deploy/vllm-gemma4 --tail=50
```

### Common Causes

**1. OOM — RTX 3090 24GB exhausted**

Logs contain: `torch.cuda.OutOfMemoryError`, `CUDA OOM`, or process killed by OOM killer.

```bash
# Check VRAM usage
kubectl exec -n xnch-system deploy/vllm-gemma4 -- nvidia-smi
```

**Fix:**
```bash
kubectl rollout restart -n xnch-system deploy/vllm-gemma4
```

If re-occurs:
- Edit `infra/k8s/i9-node/vllm-gemma4.yaml`
- Change `--gpu-memory-utilization 0.90` → `0.85`
- `kubectl apply -f infra/k8s/i9-node/vllm-gemma4.yaml`

**2. Model Load Timeout / HF Download Failure**

Logs contain: `OSError: Can't load model` or HuggingFace hub timeout.

```bash
# Check HuggingFace secret exists
kubectl get secret -n xnch-system huggingface-secret
```

**Fix:**
```bash
# Recreate if expired
kubectl delete secret -n xnch-system huggingface-secret
kubectl create secret generic huggingface-secret \
  --from-literal=token=$HF_TOKEN \
  -n xnch-system
kubectl rollout restart -n xnch-system deploy/vllm-gemma4
```

Model is cached at `/root/.cache/huggingface/`. If PVC persists across restarts, re-download is avoided.

**3. Port Conflict**

Logs contain: `address already in use` or `EADDRINUSE`.

```bash
# Check if another service grabbed port 8000 on i9
kubectl logs -n xnch-system deploy/nexi --tail=10 | grep 8000
```

**Fix:**
```bash
kubectl rollout restart -n xnch-system deploy/vllm-gemma4
```

If persistent: Nexi may have crashed and held the port. Restart Nexi first:
```bash
kubectl rollout restart -n xnch-system deploy/nexi
kubectl rollout restart -n xnch-system deploy/vllm-gemma4
```

### Verify Recovery

```bash
# 1. Pod is Running
kubectl get pods -n xnch-system -l app=vllm-gemma4
# → Running, Ready 1/1

# 2. vLLM API responds
curl http://i9-node:8000/v1/models
# → {"object":"list","data":[{"id":"gemma4:26b",...}]}

# 3. LiteLLM routes to it
curl http://i7-node:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"gemma4-local","messages":[{"role":"user","content":"ping"}]}'
# → Response from gemma4-local, not claude-judgment fallback
```

**Failure on step 2:** vLLM pod is Running but port not ready → check `kubectl logs -n xnch-system deploy/vllm-gemma4 --tail=20` for "Uvicorn running on" message. Model may still be loading (takes 2-5 min after pod start).
