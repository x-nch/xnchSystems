# FAQs

Frequently asked questions.

## General

### What is xnch?

xnch is a cognitive control plane - a local-first, privacy-first system for executing multi-agent workflows with structured memory and audit logging.

### What is Nexi?

Nexi is the decision engine that sits between Intent Parser and Plan Compiler. It generates N candidate plans, evaluates them against policies and memory context, and selects the best option.

### Do I need an LLM?

Yes, xnch + Nexi requires an LLM for option generation. You can use:
- vLLM (recommended, local)
- Ollama (local)
- OpenAI API (cloud)
- Anthropic API (cloud)

### Is my data sent to the cloud?

No, by default all data stays local. You can optionally configure cloud LLM providers, but all processing and storage happens on your machine.

## Installation

### What are the system requirements?

- Python 3.11+
- 2GB RAM (8GB recommended)
- 500MB disk space (more for memory stores)
- SQLite 3.35+

Optional:
- Redis (for KV cache)
- GPU (for vLLM)

### How do I install?

```bash
pip install xnch-cli
xnch init
```

## Usage

### How do I execute an intent?

```bash
xnch execute "Create a backup of the database"
```

### Can I test without executing?

Yes, use dry-run mode:

```bash
xnch execute "..." --dry-run
```

### How do I require human approval?

Configure in policy:
```yaml
policies:
  - name: require_approval
    rule:
      - risk_score: ">0.7"
    action: require_human_approval
```

Or use CLI flag:
```bash
xnch execute "..." --require-approval
```

## Configuration

### Where is config stored?

Default: `~/.xnch/config.yaml`

Custom: `xnch --config /path/to/config.yaml`

### How do I configure the model?

```yaml
model:
  provider: vllm
  endpoint: http://localhost:8000
  model_name: llama-3.1-8b
```

### How do I add policies?

1. Create policy file:
```yaml
policies:
  - name: my_policy
    rule:
      - action_type: delete
    action: reject
```

2. Add to config:
```yaml
nexi:
  policy_paths:
    - ~/.xnch/policies/default.yaml
    - ~/.xnch/policies/my_policy.yaml
```

## Learning

### Does learning happen automatically?

Yes, pattern extraction runs every 6 hours. You can trigger manually:

```bash
xnch learning extract
```

### Can I disable learning?

Yes:

```yaml
learning:
  enabled: false
```

### What gets learned?

- Success/failure patterns for intent + action combinations
- Context conditions that correlate with outcomes
- Evaluation dimension accuracy adjustments

### What is NOT learned?

- User intent classification (fixed)
- Security policies (never auto-generated)
- Credentials or sensitive data

## Security

### Is audit data tamper-proof?

Yes, the decision ledger uses SHA-256 chain linking. See [Audit Layer Architecture](../architecture/audit-layer.md).

### Can I delete audit logs?

No, they are append-only. You can configure retention periods for automatic archival.

## Troubleshooting

### Something's not working

1. Run diagnostics:
```bash
xnch doctor
```

2. Check logs:
```bash
xnch audit events --level=ERROR
```

3. Enable debug mode:
```bash
export XNCH_LOG_LEVEL=DEBUG
```

## Getting Help

### Where can I get more help?

- Check [Troubleshooting](troubleshooting/index.md)
- Review [Guides](../guides/index.md)
- Examine [Architecture](../architecture/index.md)