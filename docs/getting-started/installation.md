# Installation

Complete installation guide for xnch + Nexi.

## System Requirements

### Minimum
- Python 3.11+
- 2GB RAM
- 500MB disk space
- SQLite 3.35+

### Recommended
- Python 3.12+
- 8GB RAM
- 10GB disk space
- Redis (for KV cache)
- vLLM with GPU (for option generation)

## Installation Methods

### PyPI (Recommended)

```bash
pip install xnch-cli
```

### From Source

```bash
git clone https://github.com/xnch/xnch.git
cd xnch
pip install -e .
```

### Development Install

```bash
pip install -e ".[dev]"
```

## Optional Dependencies

### Memory Backends

```bash
# Redis for KV cache
pip install xnch-cli[redis]

# ChromaDB for vector index
pip install xnch-cli[chroma]
```

### LLM Providers

```bash
# vLLM support
pip install xnch-cli[vllm]

# Ollama support
pip install xnch-cli[ollama]

# OpenAI compatible
pip install xnch-cli[openai]
```

## Verification

```bash
xnch --version
xnch doctor
```

The `doctor` command checks:
- Python version
- Required packages
- Database connectivity
- Configuration validity