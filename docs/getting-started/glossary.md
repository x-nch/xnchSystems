# Glossary

---
tags:
  - #guide
  - #reference
---

Technical terms and definitions.

## A

### Audit Layer
The component responsible for recording all system events and decisions in an append-only, cryptographically verifiable log.

## B

## C

### Context Store
SQLite-based store holding current execution context, schema, and working memory.

### Context Manifest
A structured summary of current memory state loaded before option generation.

## D

### Decision Ledger
Append-only JSONL file with SHA-256 chain linking each decision to its predecessor.

### Decision Selector
Nexi sub-component that chooses the final plan from evaluated candidates.

## E

### Episodic Store
Database recording individual learning episodes: intent_class, action_type, entity_class, outcome, prediction_delta.

### Evaluator
Nexi sub-component that scores candidates across four dimensions (safety, efficiency, compliance, context_fit).

## I

### Intent
Normalized representation of user input with intent_class, action_type, entity_class, and parameters.

### Intent Interpreter
Nexi sub-component that parses raw input into structured Intent objects.

### Intent Parser
Component that converts raw user input into normalized Intent objects.

## L

### Learning Loop
System component that collects outcomes, extracts patterns, adapts scores, and generates policy candidates.

## M

### Memory Layer
Collection of storage components: Context Store, Vector Index, KV Cache, Outcome Store, Pattern Store.

### Model Adapter
Unified interface abstraction over different LLM providers (vLLM, Ollama, Claude, GPT).

## N

### Nexi Engine
Policy-aware multi-option decision engine that generates, evaluates, and selects candidate plans.

## O

### Option Generator
Nexi sub-component that uses LLM to generate N candidate plans from an intent.

### Outcome Store
Storage for historical execution outcomes used in learning.

## P

### Pattern Extractor
Scheduled job (default: every 6 hours) that analyzes episodic data and updates pattern store.

### Pattern Store
Storage for learned patterns with success_rate, confidence, observation_count, and context_signature.

### Plan Compiler
Component that compiles a selected plan into executable steps.

### Policy Filter
Nexi sub-component that removes candidates violating defined policies.

### Prediction Delta
The difference between predicted and actual outcome in an episodic record.

## S

### Score Adapter
Learning component that adjusts evaluation weights when dimension accuracy falls below threshold (0.6).

## V

### Vector Index
sqlite-vec based semantic search index for context matching. Embeddings generated locally via sentence-transformers (all-MiniLM-L6-v2).

### vLLM
High-performance LLM inference server, primary model provider for xnch.