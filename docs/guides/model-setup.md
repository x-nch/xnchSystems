# Model Provider Setup

---
tags:
  - #guide
  - #runtime
---

Configure LLM providers for xnch + Nexi.

## Supported Providers

- [vLLM](#vllm) - High-performance local inference
- [Ollama](#ollama) - Local LLM management
- [OpenAI](#openai) - OpenAI API
- [Anthropic](#anthropic) - Claude API

## vLLM (Recommended)

### Setup

1. Start vLLM server:

```bash
vllm serve llama-3.1-8b-instruct \
  --host 0.0.0.0 \
  --port 8000 \
  --tensor-parallel-size 1
```

2. Configure xnch:

```yaml
model:
  provider: vllm
  endpoint: http://localhost:8000
  model_name: llama-3.1-8b-instruct
  temperature: 0.7
  max_tokens: 2048
```

### Performance

| Metric | Value |
|--------|-------|
| Latency | ~50ms |
| Throughput | ~100 req/s |
| Memory | 16GB VRAM |

### Troubleshooting

```
Error: Connection refused to vLLM endpoint
→ Check vLLM is running: curl http://localhost:8000/v1/models
```

## Ollama

### Setup

1. Start Ollama:

```bash
ollama serve
```

2. Pull model:

```bash
ollama pull llama3
```

3. Configure xnch:

```yaml
model:
  provider: ollama
  endpoint: http://localhost:11434
  model_name: llama3
  temperature: 0.7
  max_tokens: 2048
```

### Performance

| Metric | Value |
|--------|-------|
| Latency | ~100ms |
| Throughput | ~10 req/s |
| Memory | 8GB RAM |

## OpenAI

### Setup

1. Get API key:

```bash
export OPENAI_API_KEY="sk-..."
```

2. Configure xnch:

```yaml
model:
  provider: openai
  api_key: ${OPENAI_API_KEY}
  model: gpt-4o
  temperature: 0.7
  max_tokens: 2048
```

### Cost Optimization

```yaml
model:
  provider: openai
  model: gpt-4o-mini  # Cheaper alternative
  # Use for simpler tasks
```

## Anthropic

### Setup

1. Get API key:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

2. Configure xnch:

```yaml
model:
  provider: anthropic
  api_key: ${ANTHROPIC_API_KEY}
  model: claude-3-5-sonnet-20241022
  temperature: 0.7
  max_tokens: 2048
```

## Testing Your Setup

```bash
# Test model connectivity
xnch doctor

# Test model generation
xnch model test "Hello, world"
```