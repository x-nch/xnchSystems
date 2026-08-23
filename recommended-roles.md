# Recommended Roles & Designations — ck-san

**Prepared:** 2026-08-23 · **Continuity:** refines §2 ("Target roles") of `~/xnch-agents/8b4f7289-1104-4c27-91f4-e1bf55c7727b/target-list.md` — that draft assumed a generic TS/Python full-stack profile; this version is grounded in what the `xnchSystems` repo actually proves.
**Method:** every fit claim below cites a concrete artifact in this monorepo (`docs/architecture-suite.md`, `docs/deployment-audit-2026-08-22.md`, service trees). Comp bands blend Levels.fyi/posted-range data already verified in the target list (Jun–Aug 2026) with 2026 market surveys (sources at end).

---

## What this repo proves (evidence synthesis)

ck-san solo-designed, built, and operates a production multi-service AI platform:

| Capability | Evidence |
|---|---|
| **Self-hosted LLM inference ops** | vLLM serving Ornith-1.0-35B MoE (GPTQ, `gptq_marlin` kernels, FlashAttention tuning) on consumer GPU; GPU-driver bootstrap (`setup-gpu-driver.sh`); LiteLLM model-routing gateway; Langfuse tracing (`docs/architecture-suite.md` §1–2; audit §4 rows 1–2) |
| **Agent decision architecture** | nexi 10-step governed pipeline: intent interpretation → context manifest → option generation → policy filter → evaluation/simulation → selection → action-spec compilation → verdict → dispatch → outcome callback computing `prediction_delta` written back to memory (`docs/architecture-suite.md` §4, §8) |
| **Governance / HITL** | PolicyEngine over YAML policies, DecisionLedger + audit JSONL, execution tokens, memory quarantine for trust violations, `/governance/pipeline` API with interrupts (audit §4 row 11: "done (recent)") |
| **Memory engineering** | Four-tier memory: Redis L0 sensory/L1 working → Postgres+pgvector L2 episodic (MiniLM 384-d) → Kuzu graph L3a + Postgres relationship mirror; consolidation timer with LLM triple-extraction, decay/archival; unified cross-tier tier-graph API (`architecture-suite.md` §5, §5a) |
| **Learning & evals** | Online learning loop (PatternExtractor → ScoreAdapter → PolicyCandidateGenerator, 6h cron); goals subsystem with driver loop + eval harness (audit row 12); **xnch-train**: trace/Postgres extraction → PII scrubbing/pseudonymization → dataset writer → eval harness (suites, metrics, Qwen3 XML runner against live endpoint) → promotion gate |
| **Backend engineering** | Two Python 3.13 FastAPI async services; asyncpg/psycopg, Redis, JWT public-key auth, dedup/rate-limiting, idempotent episode lifecycle; 192-test suite passing across 7 test paths (audit §4 row 3) |
| **Platform / SRE** | k3s → bare-metal two-node migration (compose + 10 systemd units), `deploy.sh` rollout automation, e2e smoke tests, boot-order/WoL orchestration, Tailscale funnel exposure, severity-ranked self-audits with remediation plans (`deployment-audit-2026-08-22.md`) |
| **Full-stack surface** | muse operator console: Next.js 16 / React 19 / TypeScript, React Flow memory-graph explorer (`/graph`), Radix + TanStack Query + Zustand, vitest (`web/package.json`) |
| **Tooling ecosystem** | MCP bridge pool spawning stdio tool servers (`xnch_mcp`, fs-read-agent, exec-agent, docs-test-mcp), crawler stack (crawlee/trafilatura), faster-whisper voice client (`pyproject.toml` entrypoints) |

The rare combination is **inference infrastructure + agent reliability/governance + eval/fine-tuning rigor**, shipped alone to production hardware — not one of these skills, all of them integrated.

---

## Role recommendations (ranked by fit strength)

### 1. AI Infrastructure Engineer
**Verbatim titles to search:** `AI Infrastructure Engineer`, `Senior AI Infrastructure Engineer`, `Software Engineer, Inference`, `Software Engineer, ML Infrastructure`, `Member of Technical Staff — Inference`

**Why it fits:** This is the single strongest match in the repo. He runs his own inference stack end-to-end: vLLM serving a quantized 35B MoE with kernel-level tuning choices (`gptq_marlin`, FlashAttention), a LiteLLM routing gateway fronting it, Langfuse tracing behind it, GPU driver bootstrap scripts, and capacity decisions (GPU memory utilization) documented in live migration notes. Most candidates claiming "AI infra" have used a hosted API; he operates the serving layer itself on his own metal.

**Seniority band:** Senior (primary); Staff at startups/inference companies (Modal/Baseten/Fireworks-class) where "owns the serving path" is the job description.

**Comp expectation (US, 2026):**
- Product/growth companies: **base $200–280K · TC $320–480K**
- Inference-platform startups & big tech: **TC $400–550K**
- Frontier labs (posted/Levels.fyi Aug '26): senior median ≈ **$591K** (Anthropic); Databricks L5 median ≈ **$667K**

---

### 2. Agent Engineer
**Verbatim titles:** `Agent Engineer`, `Senior Agent Engineer`, `Agentic AI Engineer`, `Software Engineer, Agents`, `Full Stack Engineer, Agent Platform`, `Product Engineer, AI` (Linear's exact posting name)

**Why it fits:** nexi *is* an agent platform with the parts most teams lack: a governed decision pipeline (policy filter before any action), simulation/scoring before selection, HITL interrupts via the governance pipeline, an outcome callback that closes the loop with `prediction_delta`, and MCP-based tool integration. The market's stated differentiator for this title is "reliability, guardrails, and eval harnesses for agents running unattended" — the repo demonstrates exactly that, including the learning loop that turns outcomes into policy candidates.

**Seniority band:** Senior primary. Solo ownership of multi-agent governance reads as staff-level scope; apply Staff where the req says "agent platform architecture."

**Comp expectation (US, 2026):**
- Broad market: **base $210–290K · TC $260–400K** (senior); **TC $400–600K+** (staff/lead)
- Labs & frontier wrappers: **$300–550K+**
- Remote-first dev-tools shortlist (from target list): Linear ≈ $220–340K est.; PostHog calculator ≈ $271–296K cash+equity

---

### 3. Applied AI Engineer — Evals & Fine-Tuning
**Verbatim titles:** `Applied AI Engineer`, `LLM Engineer`, `AI Evaluation Engineer`, `Machine Learning Engineer, Post-Training`, `Research Engineer` (stretch)

**Why it fits:** xnch-train is a complete Phase-0 post-training subsystem built to production hygiene standards: dataset extraction from Langfuse traces and Postgres episodes, PII scrubbing + pseudonymization before data leaves the boundary, a typed dataset writer with manifests, an eval harness with suites/metrics running against the live endpoint, and a **promotion gate** deciding whether a candidate model ships. Market surveys consistently name "demonstrable eval rigor" as the top-paid differentiator inside the AI-engineer band — this is verifiable, not claimed. The online PatternExtractor/ScoreAdapter loop adds the rarer continuous-learning angle.

**Seniority band:** Senior; Research Engineer at labs as stretch (no publications — lead with the working system instead).

**Comp expectation (US, 2026):** **base $200–280K · TC $280–420K**; fine-tuning/RAG specialization carries a reported +25–40% premium over generalist ($200–280K base commonly cited); labs higher.

---

### 4. Senior Backend / Platform Engineer (Python)
**Verbatim titles:** `Senior Software Engineer, Backend`, `Senior Backend Engineer (Python)`, `Platform Engineer`, `Senior Software Engineer, Core Services`

**Why it fits:** The control-plane work is orthodox, high-quality distributed-systems engineering: async FastAPI services with lifespan-managed state, Postgres (asyncpg/psycopg) with pgvector, Redis caching/dedup/rate limiting, JWT public-key auth, adapter-pattern clients, idempotent episode state machines, JSONL audit ledgers, 192 green tests. Carried over from target-list §2 role 2 — now with much stronger evidence than the generic assumption.

**Seniority band:** Senior (safe floor title; use when a req doesn't have an AI-flavored opening — e.g., Stripe US-Remote backend, Supabase platform/API roles from the shortlist).

**Comp expectation (US, 2026):** **TC $300–440K** at product companies (Stripe p25–median $375–440K; Datadog $350–430K per posted/Levels.fyi data); remote-first shops $220–340K.

---

### 5. ML Platform / MLOps Engineer
**Verbatim titles:** `ML Platform Engineer`, `MLOps Engineer`, `Machine Learning Systems Engineer`, `Infrastructure Engineer, ML`

**Why it fits:** The deployment-audit workstream is a platform-engineer's portfolio: orchestrated a k3s→bare-metal migration without downtime intent drift, owns compose + systemd unit topology across two nodes with dependency ordering, wrote deploy automation (`deploy.sh`) and an e2e smoke test, and authored a severity-ranked audit (boot ordering, health gating, resource limits, log rotation, secrets hygiene) with a remediation plan. He also knows *why* k3s was removed — judgment, not just tooling.

**Seniority band:** Senior. (Weaker differentiation than roles 1–3 because pure-MLOps reqs often skew toward CI/CD-and-Kubernetes generalists; use selectively.)

**Comp expectation (US, 2026):** **base $170–240K · TC $250–380K**; +15–25% premium over generalist SWE commonly cited for ML-platform specialization.

---

### 6. Founding Engineer (AI Infrastructure or Agents)
**Verbatim titles:** `Founding Engineer`, `Founding AI Engineer`, `Founding Member — Engineering`, `Founding Inference Engineer`

**Why it fits:** The entire four-subsystem suite — control plane, decision engine, training pipeline, web console, plus infra — was designed, built, tested, deployed, and audited by one person who also wrote the runbooks. That is the literal founding-engineer job: own everything, ship anyway. Seed/A-stage agent-infra companies are disproportionately founded by people with this exact profile and hire clones of it.

**Seniority band:** Senior-equivalent founding IC (employee ~1–10). Title inflation irrelevant; scope is the pitch.

**Comp expectation (US, 2026):** **base $150–220K + meaningful equity** (typical 0.5–2.0% early); TC highly variable — screen for valuation vs. dilution. Best non-comp upside of any option here.

---

### 7. Forward Deployed Engineer *(carried over from target list)*
**Verbatim titles:** `Forward Deployed Engineer`, `Forward Deployed Engineer — AI`, `Solutions Engineer, Agents`

**Why it fits:** End-to-end solo ownership from schema design through UI means he can walk into a customer environment and build the whole thing unaided — the core FDE trait. FDE listings surged >800% during 2025; labs use the ladder as a shipping-weighted entry path.

**Seniority band:** Senior.

**Comp expectation (US, 2026):** **base $200–350K** (Ramp's published band, per target list); TC spread up to ~5× driven almost entirely by private equity at labs.

### Secondary option
- **Site Reliability Engineer / Platform Engineer** — only for infra-org reqs (Datadog/Vercel-class SRE postings in the shortlist). Real evidence exists (§ Platform/SRE above) but underuses the AI depth; treat as fallback, not target.

---

## Positioning notes

1. **Lead with role 1 or 2, not "full-stack."** The original draft led with Full-Stack/Backend because no resume evidence existed. The repo shows the scarce profile is infra+agents; backend/full-stack titles price him near the median of a larger pool. Use title 3–4 as the wedge into AI-product companies lacking a dedicated infra seat.
2. **Staff applications:** submit Staff-level where the req says "platform architecture," "reliability of unattended agents," or "own the serving path" — solo production ownership compensates for level ambiguity. Elsewhere, Senior guarantees loop pass-rate.
3. **Eval-rigor story is the interview weapon.** Promotion gates, scrubbed datasets, prediction-delta feedback, and a 192-test suite answer the question every 2026 agent-team loop asks: "how do you know it works?"
4. **Constraints carried over unchanged** from target-list §3: remote-first, base ≥$180K preferred, TC target $300K+, stability screen, 15-day sprint sequencing (roles 1–2 map to day-1 applications at Anthropic/Cursor/Databricks/Vercel-AI-Gateway/PostHog-AI from §4).
5. **Known gap to pre-empt:** no CI anywhere in the repos (audit G7) and open security-hardening items (audit S1/S3). Have the remediation plan ready as a talking point — owning known gaps reads as seniority, hiding them reads as risk.

## Comp summary table (US total comp, 2026)

| # | Role family | Senior band | Staff/lab ceiling |
|---|---|---|---|
| 1 | AI Infrastructure / Inference | $320–480K | $591–667K+ |
| 2 | Agent / Agentic AI Engineer | $260–400K | $600K+ |
| 3 | Applied AI (evals/fine-tuning) | $280–420K | $500K+ |
| 4 | Senior Backend / Platform | $300–440K | $550K+ |
| 5 | ML Platform / MLOps | $250–380K | $450K+ |
| 6 | Founding Engineer | $150–220K base + heavy equity | n/a |
| 7 | Forward Deployed Engineer | $200–350K base + equity | lab equity uplift |

## Sources

- Repo artifacts: `docs/architecture-suite.md` (Aug 2026), `docs/deployment-audit-2026-08-22.md`, `xnch-train/` package tree, `web/package.json`, root `pyproject.toml`
- Continuity: `~/xnch-agents/8b4f7289-1104-4c27-91f4-e1bf55c7727b/target-list.md` (Levels.fyi Jun–Aug 2026; PostHog handbook calculator; posted ranges at Ramp/Vercel/Databricks; careers boards verified Aug 2026)
- Market surveys: KORE1 Agentic AI Hiring Survey (Jul 2026) — senior base $210–290K, staff TC $400–600K+, 15–20% agentic premium; TheAICareerLab (Jun 2026) — $185–320K base, eval rigor as top lever; HeroHunt comp analysis (Aug 2026) — $211K broad anchor, FDE surge >800%; Acceler8 Talent (Apr 2026) — MLOps +15–25%, fine-tuning/RAG +25–40% premiums
