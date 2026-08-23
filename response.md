I'll start by reading the earlier draft and getting the lay of the land in the repo, then dig into each subsystem before writing recommendations.
Draft loaded — it assumed a generic full-stack profile; now I have actual repo evidence to sharpen the roles. Let me explore the root docs and each subsystem.
Rich architecture doc — two-node self-hosted stack with vLLM serving a 35B MoE, four-tier memory, governance/audit ledger, learning loop. Now the training subsystem, web UI, and ops docs.
Now the training package and muse UI specifics.
README is stale (pre-migration k3s/Gemma era); the Aug 2026 architecture doc is authoritative. Quick pass over training modules and the two service trees to finish the evidence base.
Evidence base is solid. Quick market check on 2026 titles/comp for AI-infra and agent engineering before writing.
Market bands confirmed. Writing the deliverable now.
Written to `recommended-roles.md`. Summary of the 7 ranked recommendations:

1. **AI Infrastructure Engineer** — strongest fit (vLLM/Ornith 35B MoE serving, LiteLLM gateway, GPU ops); Senior→Staff; TC $320–480K, lab ceiling $591–667K+
2. **Agent Engineer** — nexi's governed decision pipeline + HITL interrupts + outcome feedback loop; senior TC $260–400K, staff $600K+
3. **Applied AI Engineer (Evals/Fine-Tuning)** — xnch-train's scrubbed datasets, eval harness, promotion gate; $280–420K
4. **Senior Backend/Platform Engineer (Python)** — the FastAPI/Postgres/Redis control-plane work; $300–440K
5. **ML Platform / MLOps Engineer** — k3s→bare-metal migration + self-audits; $250–380K
6. **Founding Engineer** — solo full-stack ownership is the literal job; $150–220K base + heavy equity
7. **Forward Deployed Engineer** — carried over from target-list; $200–350K base

Key upgrade over the draft: it previously led with generic full-stack titles under a "no resume on file" assumption — the repo evidence now supports leading with AI-infra and agent titles, which price at a 15–20% premium. Each recommendation cites specific repo artifacts (`docs/architecture-suite.md`, `deployment-audit-2026-08-22.md`, xnch-train package tree), with positioning notes including how to pre-empt the known gaps (no CI, secrets findings S1/S3).