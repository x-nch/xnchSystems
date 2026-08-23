# xnchSystems Documentation

Operating documentation for a solo-operated, local-first AI orchestration platform:
the **xnch** control plane and the **nexi** decision engine, deployed across two
physical nodes under a **no-k3s systemd regime**, plus the surrounding packages
(`xnch-train`, `muse` web app, `xnch_mcp` bridge, `cli` voice client).

- New here? Start at the [root README](../README.md), then
  [Architecture overview](architecture/overview.md).
- Deploying? [Deploy Node A](guides/deploy-node-a.md) · [Deploy Node B](guides/deploy-node-b.md).
- Operating HITL? [Operate approvals](guides/operate-hitl.md).
- Reference lookup? [API](reference/api-xnch.md) · [Env vars](reference/env-vars.md) · [Auth model](reference/auth-model.md).

## Terminology

| Term | Meaning |
|---|---|
| **Node A** | `gate7` (legacy alias `i7-node`), `192.168.50.1`. Control plane, memory layer, observability. Docker compose + systemd. |
| **Node B** | `xnch-core` (legacy alias `i9-node`), `192.168.50.2`. Inference (vLLM Ornith :8082) + nexi engine (:8000). Bare venv + systemd, no Docker. WoL-wakeable. |
| `xnch` | Control plane package/submodule (REST API on :8001). Env prefix `XNCH_`. |
| `nexi` | Decision engine package/submodule (:8000). Env prefix `NEXI_`. |
| `muse` | Next.js web app in `web/` — approvals queue, workflow builder, gateway proxy. |
| `xnch-train` | Local training data pipeline + eval harness (Phase 0: dry-run gate only). |
| Hybrid-B | Short-lived HMAC gateway tokens gating `/workflows/*` + `/approvals/*` writes. See [auth model](reference/auth-model.md). |
| HITL | Human-in-the-loop: propose → interrupt → approve/reject via the verdict path and approvals queue. |

Conventions: packages and services are lowercase in code font; "XNCH" appears only
inside env-var names. Node naming follows [ADR usage](adr/2026-08-22-training-subsystem.md).

## Documentation map

```
docs/
├── architecture/    What the system IS: overview, topology, memory, pipeline,
│                    workflows/HITL, data model, training, MCP bridge
├── guides/          Task-oriented HOW-TOs: dev setup, deploys, HITL ops,
│                    workflows, chat/tools, voice, eval runs
├── reference/       Lookups: REST APIs, auth model, env vars, config files,
│                    CLIs, tests
├── runbooks/        Operational procedures: restarts, GPU window, wake/sleep,
│                    smoke test, rollback
├── diagrams/        Standalone .mmd diagram sources
├── adr/             Architecture Decision Records — IMMUTABLE, linked not rewritten
└── superpowers/     Design specs & implementation plans — IMMUTABLE, linked
```

## Immutable records (link-only)

Decision history lives in these trees and is never edited:

- ADRs: [Training subsystem](adr/2026-08-22-training-subsystem.md)
- Specs: [Workflows backend design](superpowers/specs/2026-08-22-workflows-backend-design.md) (Hybrid-B §4),
  [Dynamic persona](superpowers/specs/2026-08-22-nexi-dynamic-persona-design.md),
  [HITL dark-minimalist UI](superpowers/specs/2026-08-22-xnchsystems-hitl-dark-minimalist-design.md),
  [OpenCode session ingest](superpowers/specs/2026-08-22-opencode-session-ingest-design.md)
- Plans: [Goal tracking loop](superpowers/plans/2026-08-17-goal-tracking-loop.md),
  [Training Phase 0](superpowers/plans/2026-08-22-training-subsystem-phase0.md)
- Point-in-time reviews & audits: `docs/reviews/`, `docs/deployment-audit-2026-08-22.md`,
  historical notes in `misc/`.

Where code and any prose disagree, **code wins** — flag it rather than trusting the page.
