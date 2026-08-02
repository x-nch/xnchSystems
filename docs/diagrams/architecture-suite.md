# Architecture Diagram Suite

Mermaid diagrams derived from the live **no-k3s** codebase (Aug 2026).  
Node A = `192.168.50.1` (gate7/i7). Node B = `192.168.50.2` (xnch-core/i9).

---

## 1. System Architecture

```mermaid
flowchart TB
    subgraph Clients["Clients"]
        CLI["CLI / OpenClaw"]
        OP["Operator / curl"]
    end

    subgraph NodeA["Node A — 192.168.50.1 (control + memory)"]
        subgraph DockerA["Docker Compose"]
            LLM["LiteLLM :4000"]
            RD["Redis :6379"]
            PG["Postgres + pgvector :5432"]
            LF["Langfuse :3000"]
        end

        subgraph SystemdA["systemd"]
            XNCH["xnch :8001<br/>FastAPI gateway"]
            CONS["consolidation.timer<br/>POST /admin/consolidate"]
        end

        KUZU["Kuzu graph<br/>~/.xnch/graph.kuzu"]
        SQLITE["SQLite governance<br/>~/.xnch/data/episodic.db"]
        AUDIT["Audit JSONL<br/>events + decisions"]
    end

    subgraph NodeB["Node B — 192.168.50.2 (inference + decision)"]
        subgraph SystemdB["systemd"]
            VLLM["vllm-ornith :8082<br/>Ornith-1.0-35B MoE"]
            NEXI["nexi :8000<br/>decision pipeline"]
        end
    end

    CLI --> XNCH
    OP --> XNCH

    XNCH <-->|"session/init, memory, verdict"| NEXI
    XNCH --> RD
    XNCH --> PG
    XNCH --> KUZU
    XNCH --> SQLITE
    XNCH --> AUDIT
    XNCH -->|"POST /v1/chat/completions"| LLM
    XNCH -->|"POST /nexi/chat"| LLM

    LLM -->|"api_base"| VLLM
    NEXI -->|"XNCH_XNCH_BASE_URL"| XNCH
    NEXI -->|"redis/postgres (remote)"| RD
    NEXI -->|"redis/postgres (remote)"| PG
    NEXI -->|"execution dispatch"| XNCH

    CONS --> XNCH
    LF -.->|"LLM traces"| LLM
```

---

## 2. Infrastructure

```mermaid
flowchart LR
    subgraph Boot["Boot order"]
        S1["start-node-a.sh"]
        S2["start-node-b.sh"]
        S3["e2e-test.sh"]
        S1 --> S2 --> S3
    end

    subgraph NodeA["Node A — gate7 / i7 / 192.168.50.1"]
        direction TB
        DC["docker compose up -d<br/>infra/no-k3s/node-a"]
        DC --> litellm["litellm :4000"]
        DC --> redis["redis :6379"]
        DC --> pgvec["postgres-pgvector :5432"]
        DC --> langfuse["langfuse :3000"]
        DC --> lfpgs["langfuse-postgres :5433"]

        SYSA["systemd enable+start"]
        SYSA --> xnch_svc["xnch.service :8001"]
        SYSA --> cons_svc["consolidation.timer"]

        ENV_A["~/.xnch/xnch.env"]
    end

    subgraph NodeB["Node B — xnch-core / i9 / 192.168.50.2"]
        direction TB
        SYSB["systemd enable+start"]
        SYSB --> vllm_svc["vllm-ornith.service :8082"]
        SYSB --> nexi_svc["nexi.service :8000"]
        vllm_svc --> nexi_svc

        ENV_B["~/.xnch/nexi.env"]
        MODEL["~/models/ornith-gptq-pro"]
        VENV["~/venvs/vllm-ornith"]
    end

    S1 --> DC
    S1 --> SYSA
    S2 --> SYSB

    nexi_svc -->|"XNCH_XNCH_BASE_URL"| xnch_svc
    nexi_svc -->|"NEXI_REDIS_URL / NEXI_POSTGRES_URL"| redis
    nexi_svc -->|"NEXI_POSTGRES_URL"| pgvec
    litellm -->|"api_base http://192.168.50.2:8082/v1"| vllm_svc
    xnch_svc --> redis
    xnch_svc --> pgvec
    xnch_svc --> litellm
```

---

## 3. xnch (Control Plane)

```mermaid
flowchart TB
    subgraph API["FastAPI — xnch.main :8001"]
        HEALTH["GET /health"]
        STATE["GET /system/state"]

        SESS["/session/init<br/>/session/{id}/clarify"]
        MEM["/memory/read<br/>/memory/write"]
        VER["POST /verdict"]
        EXEC["/execution/execute<br/>/execution/outcome"]
        GOV["/governance/*<br/>/auth/public-key"]
        GW["/nexi/chat<br/>/nexi/memory/recall<br/>/nexi/system-prompt"]
        CHAT["POST /v1/chat/completions"]
        ADM["POST /admin/consolidate"]
    end

    subgraph Core["App state (lifespan)"]
        AUTH["Auth + GovernanceStore"]
        POL["PolicyEngine + PolicyLoader"]
        KV["KVCache (Redis)"]
        SB["SensoryBuffer L0"]
        WM["WorkingMemory L1"]
        PGE["PgEpisodicStore L2"]
        GS["GraphStore L3 Kuzu"]
        RS["RelationshipStore PG"]
        EP["EpisodicStore SQLite"]
        PAT["PatternStore SQLite"]
        LEARN["PatternExtractor<br/>ScoreAdapter<br/>PolicyCandidateGenerator"]
        LOG["EventLog + DecisionLedger"]
    end

    SESS --> AUTH
    SESS --> KV
    SESS -->|"forward"| NEXI_EXT["nexi :8000 /session/start"]

    MEM --> PGE
    MEM --> PAT
    MEM --> POL

    VER --> POL
    VER --> LOG
    VER --> EP
    VER --> PGE

    EXEC --> EP
    EXEC --> PGE
    EXEC -->|"callback"| NEXI_EXT

    GW --> WM
    GW --> PGE
    GW --> GS
    GW --> RS
    GW --> SB
    GW -->|"LiteLLM"| LLM_EXT["litellm :4000"]

    ADM --> CONS_JOB["jobs/consolidation.py"]
    CONS_JOB --> PGE
    CONS_JOB --> GS
    CONS_JOB --> RS

    LEARN --> PGE
    LEARN --> PAT
```

---

## 4. nexi (Decision Engine)

```mermaid
flowchart TB
    subgraph Entry["POST /session/start"]
        S1["1. IntentInterpreter<br/>rules + Redis recall + LLM"]
        S2["2. load_context<br/>xnch POST /memory/read"]
        S3["3. generate_options<br/>ModelAdapter → LiteLLM/vLLM"]
        S4["4. PolicyFilter<br/>xnch POST /policy/check"]
        S5["5. Evaluator<br/>score + simulate"]
        S6["6. select_decision"]
        S7["7. compile_action_spec"]
        S8["8. submit_verdict<br/>xnch POST /verdict"]
        S9["9. dispatch_execution<br/>xnch POST /execution/execute"]
        S10["10. return EXECUTING"]
    end

    subgraph Callback["POST /callback/outcome"]
        C1["compute prediction_delta"]
        C2["xnch POST /memory/write<br/>EPISODE_PREDICTION_UPDATE"]
    end

    subgraph Adapters["Adapters"]
        XC["XnchClient"]
        MA["ModelAdapter"]
    end

    S1 --> S2 --> S3 --> S4 --> S5 --> S6 --> S7 --> S8 --> S9 --> S10
    S2 --> XC
    S4 --> XC
    S8 --> XC
    S3 --> MA
    S9 -->|"stub runner"| XNCH_EXEC["xnch /execution/execute"]
    XNCH_EXEC -->|"async callback"| C1 --> C2
```

---

## 5. Memory Evolution

```mermaid
flowchart TB
    subgraph Legacy["Retired / superseded"]
        K3S["k3s cluster layout"]
        CHROMA["ChromaDB / agentmemory"]
        MEM0["mem0"]
        ZEP["Zep"]
        GEMMA["Gemma 4 26B primary"]
    end

    subgraph Current["Current four-tier stack"]
        L0["L0 SensoryBuffer<br/>Redis TTL ~60s"]
        L1["L1 WorkingMemory<br/>Redis session turns"]
        L2["L2 PgEpisodicStore<br/>Postgres + pgvector MiniLM 384d"]
        L3A["L3a Kuzu GraphStore<br/>entities + relations"]
        L3B["L3b relationship_memory<br/>Postgres mirror"]
    end

    subgraph WriteSources["Write sources"]
        CHAT_W["/nexi/chat → store_episode"]
        VERDICT_W["/verdict → decision_episodes"]
        OUTCOME_W["/execution/outcome → complete episode"]
        IDENTITY["cold_start_seeder identity facts"]
        INGEST["conversation ingest / ops memory"]
    end

    subgraph Consolidation["Consolidation (timer + /admin/consolidate)"]
        EXTRACT["graph_extractor<br/>LiteLLM ornith → triples"]
        DECAY["decay_score + archive<br/>threshold 0.1"]
    end

    subgraph Learning["Learning loop (6h cron)"]
        PE["PatternExtractor"]
        SA["ScoreAdapter"]
        PCG["PolicyCandidateGenerator"]
    end

    K3S -.->|"migrated"| Current
    CHROMA -.-> L2
    GEMMA -.->|"replaced by"| VLLM["vLLM Ornith :8082"]

    CHAT_W --> L1
    CHAT_W --> L2
    VERDICT_W --> L2
    OUTCOME_W --> L2
    IDENTITY --> L2
    INGEST --> L2

    L2 --> EXTRACT
    EXTRACT --> L3A
    EXTRACT --> L3B
    L2 --> DECAY

    L2 --> PE --> PAT["patterns table"]
    PAT --> SA
    PAT --> PCG

    L0 -.->|"promoted on activity"| L1
    L1 -.->|"semantic recall"| L2
    L3A -.->|"entity context"| CA["context_assembler"]
    L2 -.-> CA
```

---

## 6. Schema

Eight tables across Postgres, Kuzu, and SQLite. Split into four diagrams so field labels stay fully visible in preview.

### 6a. Postgres L2 — episodic core

```mermaid
erDiagram
  episodes {
    uuid id PK
    text type
    text raw_text
    text summary
    vector384 embedding
    float importance
    int recall_count
    timestamptz last_recalled
    float decay_score
    boolean archived
    timestamptz timestamp
    timestamptz created_at
  }

  decision_episodes {
    uuid episode_id PK
    text decision_id
    text intent_class
    text action_type
    text entity_class
    text actor_role
    text outcome
    float prediction_delta
    boolean early_reextraction_flag
    jsonb context_snapshot
    jsonb scores_json
    text generation_path
    timestamptz created_at
    timestamptz completed_at
  }

  patterns {
    uuid pattern_id PK
    text context_signature UK
    text intent_class
    text action_type
    text entity_class
    text actor_role
    float success_rate
    float confidence
    int observation_count
    float avg_prediction_delta
    text extraction_run_id
    timestamptz created_at
    timestamptz updated_at
  }

  episodes ||--o| decision_episodes : decision_id
  decision_episodes }o--|| patterns : tuple_agg
```

### 6b. Postgres — relationships and quarantine

```mermaid
erDiagram
  episodes {
    uuid id PK
    text type
    text summary
  }

  relationship_memory {
    uuid id PK
    text entity_a_id
    text entity_b_id
    text relationship_type
    float strength
    text_array evidence
    timestamptz first_seen
    timestamptz last_reinforced
    int reinforcement_count
  }

  quarantine_memories {
    uuid id PK
    text memory_type
    text raw_text
    text summary
    float importance
    text quarantine_reason
    text quarantined_by
    text original_actor_role
    text original_trust_level
    timestamptz created_at
    timestamptz released_at
    text released_by
  }

  episodes ||--o{ relationship_memory : consolidation
  episodes ||--o| quarantine_memories : quarantine
```

### 6c. Kuzu L3a — graph store

File: `~/.xnch/graph.kuzu`

```mermaid
erDiagram
  entities {
    string entity_id PK
    string name
    string type
    timestamp created_at
  }

  relations {
    string rel_type
    double confidence
    timestamp created_at
  }

  entities ||--o{ relations : connects
```

### 6d. SQLite — governance episodic

File: `~/.xnch/data/episodic.db` (verdict path; mirrors decision tuple)

```mermaid
erDiagram
  sqlite_episodes {
    text episode_id PK
    text decision_id
    text intent_class
    text action_type
    text entity_class
    text actor_role
    text outcome
    real prediction_delta
    int early_reextraction_flag
    text context_snapshot
    text generation_path
    real created_at
    real completed_at
    text schema_version
  }
```

### Cross-store links

```mermaid
flowchart LR
  PG_EP["Postgres episodes"]
  PG_REL["relationship_memory"]
  KUZU["Kuzu relations"]
  SQLITE["SQLite episodes"]

  PG_EP -->|"consolidation"| PG_REL
  PG_REL -.->|"mirror"| KUZU
  PG_EP -.->|"verdict open/close"| SQLITE
```


---

## 7. Read Sequence Path

Covers decision-loop read (`/memory/read`), chat recall (`/nexi/chat`), and direct recall (`/nexi/memory/recall`).

```mermaid
sequenceDiagram
    autonumber
    participant User
    participant XNCH as "xnch :8001"
    participant NEXI as "nexi :8000"
    participant Redis as "Redis L0/L1"
    participant PG as "Postgres pgvector"
    participant Graph as "Kuzu + relationship_memory"
    participant LiteLLM as "LiteLLM :4000"
    participant VLLM as "vLLM Ornith :8082"

    rect rgb(240, 248, 255)
        Note over User,NEXI: Decision path — context manifest
        User->>XNCH: POST /session/init
        XNCH->>XNCH: auth, dedup, rate limit
        XNCH->>NEXI: POST /session/start
        NEXI->>NEXI: IntentInterpreter (rules + Redis cache, LLM fallback)
        opt LLM classify
            NEXI->>LiteLLM: classify intent (ornith)
            LiteLLM->>VLLM: inference
            VLLM-->>LiteLLM: intent JSON
            LiteLLM-->>NEXI: classified Intent
        end
        NEXI->>XNCH: POST /memory/read
        XNCH->>PG: fetch_for_manifest(tuple, lookback)
        XNCH->>PG: fetch_patterns_for_manifest(tuple)
        XNCH->>XNCH: build policy refs
        XNCH-->>NEXI: ContextManifest (episodes, patterns, policies)
        NEXI->>LiteLLM: generate_options (ornith)
        LiteLLM->>VLLM: inference
        VLLM-->>LiteLLM: option payloads
        LiteLLM-->>NEXI: PlanOptions
    end

    rect rgb(255, 250, 240)
        Note over User,VLLM: Chat path — semantic recall
        User->>XNCH: POST /nexi/chat
        XNCH->>XNCH: injection_guard.scan_input
        Note over XNCH: assemble_context()
        XNCH->>Redis: working_memory.get_turns(20)
        XNCH->>PG: retrieve_similar(query, top_k=5)
        PG-->>XNCH: episodes + similarity scores
        XNCH->>Graph: entity mentions → connections + relationships
        XNCH->>PG: bump_recall(episode ids)
        XNCH->>Redis: sensory_buffer.read_recent(voice)
        XNCH->>XNCH: build_system_prompt → AssembledContext
        XNCH->>XNCH: classify_request → model route
        XNCH->>Redis: append_turn(user message)
        XNCH->>LiteLLM: POST /chat/completions
        LiteLLM->>VLLM: forward
        VLLM-->>LiteLLM: response tokens
        LiteLLM-->>XNCH: completion
        XNCH-->>User: response JSON
    end

    rect rgb(240, 255, 240)
        Note over User,Graph: Direct recall API
        User->>XNCH: POST /nexi/memory/recall
        XNCH->>PG: retrieve_similar(query, top_k)
        PG-->>XNCH: ranked episodes
        XNCH->>Graph: enrich with relationships (optional)
        XNCH-->>User: episodes + similarity + relationships
    end
```

---

## 8. Write Sequence Path

Covers chat episodes, verdict decision episodes, execution outcomes, and learning writes.

```mermaid
sequenceDiagram
    autonumber
    participant User
    participant XNCH as xnch :8001
    participant NEXI as nexi :8000
    participant Guard as memory_guard
    participant Redis as Redis L1
    participant PG as Postgres
    participant SQLite as SQLite episodic
    participant Ledger as DecisionLedger
    participant Runner as /execution/execute

    rect rgb(255, 250, 240)
        Note over User,PG: Chat write
        User->>XNCH: POST /nexi/chat
        XNCH->>XNCH: LiteLLM inference
        XNCH->>Redis: append_turn(user + assistant)
        XNCH->>Guard: validate_memory_write
        Guard-->>XNCH: allow / block
        XNCH->>PG: store_episode(type=conversation)
        XNCH->>XNCH: invalidate system-prompt cache
    end

    rect rgb(240, 248, 255)
        Note over NEXI,PG: Decision episode open
        NEXI->>XNCH: POST /verdict
        XNCH->>XNCH: policy_engine.evaluate (authoritative)
        XNCH->>Ledger: write ALLOW/BLOCK
        XNCH->>SQLite: create_episode PENDING
        XNCH->>PG: store_decision_episode
        XNCH-->>NEXI: execution_token + audit_ref
    end

    rect rgb(240, 255, 240)
        Note over NEXI,PG: Execution outcome close
        NEXI->>Runner: POST /execute (dispatch)
        Runner->>XNCH: POST /execution/outcome SUCCESS
        XNCH->>SQLite: complete_episode
        XNCH->>PG: complete_decision_episode
        XNCH->>NEXI: async POST /callback/outcome
        NEXI->>XNCH: POST /memory/write EPISODE_PREDICTION_UPDATE
        XNCH->>PG: write_prediction_update
        opt early_reextraction_flag
            XNCH->>XNCH: pattern_extractor.run()
        end
    end

    rect rgb(248, 240, 255)
        Note over XNCH,PG: Consolidation write (scheduled)
        XNCH->>XNCH: POST /admin/consolidate
        XNCH->>PG: fetch episodes for graph extraction
        XNCH->>XNCH: graph_extractor → LiteLLM ornith
        XNCH->>PG: relationship_memory upsert
        XNCH->>XNCH: Kuzu upsert_entity/relation
        XNCH->>PG: apply_decay + archive
    end
```

---

## Related files

| Path | Purpose |
|------|---------|
| `infra/no-k3s/node-a/start-node-a.sh` | Node A boot |
| `infra/no-k3s/node-b/start-node-b.sh` | Node B boot |
| `infra/no-k3s/e2e-test.sh` | Stack smoke test |
| `xnch/main.py` | Control plane composition |
| `nexi/main.py` | Decision pipeline steps 3–12 |
| `xnch/memory/pg_episodic_store.py` | L2 schema owner |
| `nexi/pipeline/context_assembler.py` | Chat read assembly |
