---
source: techStach.md
merged: 2026-04-18
---

# Tech Stack

## Core

| Component | Technology | Why |
|-----------|------------|-----|
| Language | Python 3.11+ | AI/ML ecosystem native |
| Runtime | CPython via pyenv | Performance + asyncio maturity |
| CLI | Typer | Type hints → CLI, zero boilerplate |
| API | FastAPI + Uvicorn | Async + Pydantic v2 + OpenAPI |
| Data validation | Pydantic v2 | 5-50x faster than v1 |

---

## Memory & Storage

| Component | Technology | Why |
|-----------|------------|-----|
| Primary store | SQLite (WAL) | Zero infra, millions of rows |
| Vector search | sqlite-vec | Vector inside SQLite |
| Embeddings | sentence-transformers | CPU-based, 384-dim |
| Cache | Redis (unix socket) | Session state, rate limiting |

---

## Model Layer

| Component | Technology | Why |
|-----------|------------|-----|
| Primary model | Mistral-7B-Instruct-v0.3 (fp16) | Strong instruction following |
| Runtime | vLLM | PagedAttention, guided JSON |
| Fallback | Mistral-7B-GPTQ (4-bit) | Lower VRAM |
| CPU fallback | llama-cpp-python | Self-contained |

---

## Learning Layer

- **Pattern extraction**: APScheduler (6h interval)
- **Weight adaptation**: Versioned JSON config
- **No model training**: Pure statistical adaptation

---

## Auth & Security

- JWT: python-jose with RS256
- Execution tokens: xnch-signed, TTL-bounded
- Token validation: Execution runner validates independently

---

## Observability

- Logging: structlog (JSON output)
- Tracing: trace_id propagation via headers
- Audit: Append-only SQLite + UDP fire-and-forget
- Health: JSON endpoints per service

---

## Process Management

- supervisord (single config file, process restart)
- One worker per service (single-user system)

---

## Minimal Dependencies (12 core + 3 dev)

```
fastapi, uvicorn, pydantic, typer, httpx
sqlite-utils, sqlite-vec, openai, llama-cpp-python
sentence-transformers, python-jose, apscheduler, structlog
sse-starlette
```

Dev: pytest, pytest-asyncio, httpx