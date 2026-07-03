# GPU State — Live Cluster 2026-06-28

## GPU Inventory

### Node: gate7 (i7-9750H)
| GPU | Expected | Actual Status |
|-----|----------|---------------|
| NVIDIA GeForce GTX 1650 | Present in hardware | **Driver not installed** — `nvidia-smi` fails completely |

The nvidia-device-plugin DaemonSet runs on gate7 but cannot advertise GPU resources because no NVIDIA driver is loaded. The pod runs but the GPU is **not usable** by Kubernetes workloads.

### Node: xnch-core (i9-14900K)
| GPU | Driver | CUDA | VRAM Total | VRAM Used | VRAM Free |
|-----|--------|------|------------|-----------|-----------|
| NVIDIA GeForce RTX 3090 | 590.48.01 | 13.1 | 24,576 MiB | 20,940 MiB | 3,188 MiB |

## VRAM Breakdown

| Component | VRAM (MiB) | % of Total |
|-----------|------------|------------|
| **llama-server (PID 58345)** | 20,930 | 85.2% |
| Reserved (driver/firmware) | 450 | 1.8% |
| Free | 3,188 | 13.0% |
| **Total** | **24,576** | **100%** |

### GPU Utilization at time of inspection
- SM (streaming multiprocessor): 0%
- Memory bandwidth: 0%
- Encoder/Decoder: 0%
- **GPU is idle** — no active inference requests

## Inference Stack

### Process
```
llama-server (PID 58345)
  Path: /home/x-nch/llama-cpp-turboquant-gemma4/build/bin/llama-server
  Service: gemma4-llama.service (systemd)
  Port: :8080 (listening on 0.0.0.0)
  Started by: x-nch user on host (NOT in Kubernetes)
```

### Loaded Model
```
Model: gemma-4-26B-A4B-it-Q4_K_M.gguf
Format: GGUF
Architecture: Gemma 4 (26B parameters, 4-bit quantized)
Runtime: llama.cpp
Size on disk: 16.7 GiB (parameter size: 25.2B params)
Context length: 262,144 tokens
```

### Performance Benchmarks

| Metric | Value |
|--------|-------|
| Prompt processing | 19.5 tok/s (51ms/token) |
| Token generation | **97.4 tok/s** (10.3ms/token) |
| Prompt test size | 1 token |
| Generation test size | 10 tokens |
| Total latency (simple) | ~154ms |

### API Endpoint
- Health: `GET http://localhost:8080/health` → `{"status":"ok"}`
- Models: `GET http://localhost:8080/v1/models`
- Completions: `POST http://localhost:8080/v1/completions`
- Service type: OpenAI-compatible API (llama.cpp server)

## GPU-to-K8s Integration

### Service: vllm-gemma4 (xnch-system)
```
Name: vllm-gemma4
Type: ClusterIP (10.43.237.186)
Port: 8000 → TargetPort: 8080
Selector: NONE (no pods selected)
Endpoint: 192.168.50.2:8080 (xnch-core host IP)
```

**Critical Architecture Note:** The GPU inference endpoint is NOT managed by Kubernetes. It is:
1. Running as a systemd service (gemma4-llama.service) on the host
2. Accessed via a Kubernetes Service with no selector and a manual Endpoint
3. Not scalable, not health-checked by Kubernetes, not monitored

### Why not in K8s?
The llama-server is likely run outside Kubernetes because:
- GPU memory oversubscription would cause pod OOM kills
- llama.cpp doesn't natively support the Kubernetes device plugin protocol
- The 26B model uses 20.9GB of 24GB VRAM, leaving only 3GB headroom

## Composite GPU Memory Pressure

The GPU is at **85% VRAM utilization at idle** (20.9/24.5GiB used). This leaves only:
- **3.1 GiB free** for concurrent inference requests
- Insufficient for loading a second model
- Any memory leak in llama-server could cause OOM

## GPU-Related DaemonSets

| DaemonSet | Nodes | Status | Image |
|-----------|-------|--------|-------|
| nvidia-device-plugin-daemonset | gate7 (no driver), xnch-core (driver) | Both Running | `nvcr.io/nvidia/k8s-device-plugin:v0.14.0` |

Note: The DaemonSet on gate7 is **non-functional** — it runs but cannot discover or advertise any GPU resources due to missing NVIDIA driver. It should be removed or gate7 should have the driver installed.
