---
source: infra/localInfraDesign2.md
merged: 2026-04-18
---

# Infrastructure Design

## 1. Process Architecture

Two nodes. Clear separation. Primary does all heavy work. Secondary is overflow and lightweight model serving only.

---

### Primary Node (i9 + RTX 3090)

| Process | Port | GPU? | Role |
|---------|------|------|------|
| xnch-server | 8100 | No | Control plane API (FastAPI) |
| nexi-engine | 8200 | No | Decision engine (FastAPI) |
| vllm-primary | 8300 | Yes | Main LLM inference (3090, ~18GB) |
| memory-store | 8400 | No | SQLite + pattern store |
| execution-runner | 8500 | No | Action executor |
| audit-logger | 8600 | No | Append-only audit sink |

---

### Secondary Node (i7 + GTX 1650) — Optional

| Process | Port | GPU? | Role |
|---------|------|------|------|
| vllm-secondary | 8300 | Yes | Fallback model inference |
| nexi-worker | 8201 | No | Overflow reasoning worker |

---

## 2. Model Execution

### RTX 3090 — Primary

- Model: Mistral-7B-Instruct-v0.3 (fp16)
- VRAM: ~14GB loaded, 18GB ceiling (0.75 utilization)
- Context: 8192 tokens

### GTX 1650 — Fallback

- Model: Mistral-7B-Instruct-v0.1-GPTQ (4-bit)
- VRAM: ~3.5GB, 4GB ceiling
- Context: 4096 tokens

### CPU — Last Resort

- Runtime: llama-cpp-python
- Speed: ~8-15 tok/s on i9

---

## 3. Inter-Process Communication

All HTTP over localhost. No message queue on day 1.

```
CLI → nexi (8200) → xnch (8100) → memory (8400)
                     ↘ vllm (8300)
                     ↘ execution (8500) → xnch (8100)
```

---

## 4. Resource Management

### VRAM Allocation (3090)

- OS/display: ~1GB
- vllm ceiling: 18GB (0.75 utilization)
- Headroom: 5GB
- Total: 24GB

### SQLite

- WAL mode enabled
- Three databases: episodic.db, semantic.db, policy.db

---

## 5. Directory Structure

```
~/.xnch/
├── config.yaml
├── keys/
│   ├── private.pem
│   └── public.pem
├── data/
│   ├── episodic.db
│   ├── semantic.db
│   └── policy.db
├── policies/
├── models/
├── logs/
└── backups/
```

---

## 6. Startup Sequence

1. vllm-primary (3090) — wait 60-90s for load
2. memory-store (8400)
3. xnch-server (8100)
4. nexi-engine (8200)
5. execution-runner (8500)
6. audit-logger (8600)