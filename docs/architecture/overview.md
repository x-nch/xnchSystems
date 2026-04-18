# System Architecture

High-level overview of the xnch + Nexi system.

## System Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         xnch CLI                                │
│                    (Human Entry Point)                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Input Ingestion                            │
│                 (Typer + Rich Console)                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Intent Parser                               │
│              (Raw Input → Normalized Intent)                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Nexi Engine                                │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Intent Interpreter → Option Generator → Policy Filter │   │
│  │  → Evaluator → Decision Selector                        │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Model Adapter                               │
│            (vLLM / Ollama / Claude / GPT)                      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Memory Layer                               │
│  ┌──────────┐ ┌──────────┐ ┌────────┐ ┌──────────┐            │
│  │ Context  │ │ Vector   │ │  KV    │ │ Outcome  │            │
│  │ Store    │ │ Index    │ │ Cache  │ │ Store    │            │
│  │ (SQLite) │ │(ChromaDB)│ │(Redis) │ │          │            │
│  └──────────┘ └──────────┘ └────────┘ └──────────┘            │
│  ┌──────────┐                                                    │
│  │ Pattern  │                                                    │
│  │ Store    │                                                    │
│  └──────────┘                                                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Audit Layer                               │
│  ┌──────────────┐ ┌─────────────────┐ ┌────────────┐          │
│  │  Event Log   │ │ Decision Ledger │ │ Replay     │          │
│  │  (Append-only)│ │ (JSONL+SHA256)  │ │ Engine     │          │
│  └──────────────┘ └─────────────────┘ └────────────┘          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Learning Loop                               │
│  ┌─────────────┐ ┌───────────────┐ ┌──────────────┐            │
│  │  Outcome    │ │    Pattern    │ │   Score      │            │
│  │  Collector  │ │   Extractor   │ │   Adapter    │            │
│  └─────────────┘ └───────────────┘ └──────────────┘            │
└─────────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility |
|-----------|----------------|
| xnch CLI | Primary human entry point via Typer CLI |
| Intent Parser | Converts input to normalized Intent objects |
| Nexi Engine | Policy-aware multi-option decision engine |
| Model Adapter | Unified interface to LLM providers |
| Memory Layer | Context, vectors, cache, outcomes, patterns |
| Audit Layer | Event logging, decision ledger, replay |
| Learning Loop | Outcome collection, pattern extraction, adaptation |

## Design Principles

1. **Local-First**: All data processing happens locally by default
2. **Privacy-First**: No telemetry, no external dependencies for core functionality
3. **Audit Everything**: Complete decision trail with cryptographic verification
4. **Learning Continuously**: Patterns extracted and scores adapted over time
5. **Modular Interfaces**: Model adapter allows swapping LLM providers