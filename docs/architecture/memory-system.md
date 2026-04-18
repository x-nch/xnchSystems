---
source: memory/memoryAndEvolveArchitecture.md + architecture docs
merged: 2026-04-18
---

# Memory System Architecture

## Overview

The memory system is not a log. It is a structured, queryable, evolving knowledge graph that reflects system state, prior decisions, outcomes, and learned policies. It feeds Nexi, not models directly.

---

## Components

### Context Store (SQLite WAL)

Typed entity storage with SQLite WAL persistence.

**Schema:**
- Entity types: Decision, Observation, Constraint, Relationship
- Every record has: entity ID, timestamp, actor, action type, verdict, policy reference, content hash
- Queryable by Policy Engine at verdict time

**Key features:**
- WAL mode for concurrent reads
- JSON1 extension for semi-structured data
- Schema-versioned via migrations

---

### Vector Index (sqlite-vec)

Semantic retrieval for similar past decisions.

- Embeddings via sentence-transformers (all-MiniLM-L6-v2, 22MB, CPU)
- Similarity matching on context signatures
- Used when exact tuple matching returns no results

---

### KV Cache (Redis Unix Socket)

Session state and rate-limiting.

- Fast lookups for hot data
- TTL-based session management
- Rate limiting per actor

---

### Episodic Store

Records every decision with outcome for learning.

**Schema:**
- episode_id, intent_class, action_type, entity_class
- outcome: SUCCESS | PARTIAL | FAILURE
- prediction_delta: (predicted vs actual)
- timestamp

Episodes start PENDING, completed by execution outcome callback.

---

### Pattern Store

Aggregated patterns from episodic history.

**Schema:**
- context_signature (hash of intent + context)
- success_rate, confidence
- observation_count
- avg_prediction_delta

Updated by Pattern Extractor every 6 hours.

---

## Learning Layer

### Pattern Extractor

Runs every 6 hours via APScheduler. Groups episodes, computes success_rate + confidence per (action_type, entity_class) tuple.

### Score Adapter

Adjusts weight configs when dimension prediction accuracy < 0.6. Changes are versioned and logged.

### Policy Candidate Generator

Promotes high-confidence patterns to soft policy rules. Requires operator review before activation.

---

## Key Principles

1. **Memory is updated after execution, not after generation** — learn from what happened, not what the model said
2. **Memory does not flow directly to models** — flows to Nexi, which decides what to surface
3. **Structured state, not context window** — typed entities, not blobs
4. **Feedback loop is grounded** — prediction_delta tracks accuracy