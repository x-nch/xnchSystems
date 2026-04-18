# Model Adapter

---
tags:
  - #component
  - #runtime
  - #nexi
---

Unified interface to LLM providers.

## Overview

The Model Adapter provides a unified interface to different LLM providers (vLLM, Ollama, Claude, GPT). This allows swapping backends without changing the rest of the system.

## Supported Providers

| Provider | Description | Use Case |
|----------|-------------|----------|
| vLLM | High-performance local inference | Production, low latency |
| Ollama | Local LLM management | Development, privacy |
| OpenAI | OpenAI API compatible | Cloud, simplicity |
| Anthropic | Claude API | High-quality reasoning |

## Configuration

```yaml
model:
  provider: vllm  # vllm, ollama, openai, anthropic
  
  # Provider-specific config
  vllm:
    endpoint: http://localhost:8000
    model_name: llama-3.1-8b
    temperature: 0.7
    max_tokens: 2048
    
  ollama:
    endpoint: http://localhost:11434
    model_name: llama3
    
  openai:
    api_key: ${OPENAI_API_KEY}
    model: gpt-4
    base_url: https://api.openai.com/v1
    
  anthropic:
    api_key: ${ANTHROPIC_API_KEY}
    model: claude-3-opus
```

## Usage

```python
from xnch.models import ModelAdapter

adapter = ModelAdapter(config)

# Generate text
response = adapter.generate(
    prompt="Your prompt here",
    temperature=0.7,
    max_tokens=2048
)

# Chat completion
response = adapter.chat(
    messages=[
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Hello!"}
    ]
)
```

## API Reference

```python
class ModelAdapter(ABC):
    @abstractmethod
    def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs
    ) -> str:
        """Generate text from prompt."""
        
    @abstractmethod
    def chat(
        self,
        messages: List[ChatMessage],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs
    ) -> ChatResponse:
        """Chat completion."""


class vLLMAdapter(ModelAdapter):
    def __init__(self, endpoint: str, model_name: str):
        ...


class OllamaAdapter(ModelAdapter):
    def __init__(self, endpoint: str, model_name: str):
        ...
```

## Error Handling

| Error | Handling |
|-------|----------|
| Connection timeout | Retry 3x with exponential backoff |
| Rate limit | Wait and retry with backoff |
| Invalid model | Raise configuration error |
| API error | Log and raise with details |

## Performance

| Provider | Latency | Throughput |
|----------|---------|-------------|
| vLLM | ~50ms | ~100 req/s |
| Ollama | ~100ms | ~10 req/s |
| OpenAI | ~500ms | Rate limited |
| Anthropic | ~500ms | Rate limited |