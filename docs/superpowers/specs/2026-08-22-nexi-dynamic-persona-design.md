# Design: Dynamic Persona Self-Narrative for Nexi

**Date:** 2026-08-22
**Status:** Draft — awaiting review
**Scope:** nexi submodule (`nexi/character/`, `nexi/main.py`, `nexi/config.py`, `nexi/pipeline/context_assembler.py` consumers unchanged)

## 1. Problem & Goals

Nexi's persona is static: `nexi/character/persona.yaml` hand-codes identity traits,
including volatile tech specifics ("vLLM Ornith-1.0-35B, pgvector, Kuzu, LiteLLM,
Langfuse, no-k3s two-node layout") that drift as infra evolves. Meanwhile capabilities
are already dynamic via `capability_builder.py`, but nothing tells Nexi *what it has
been building* or *what it has recently become capable of*.

**Goal:** an auto-generated **self-narrative layer** — derived from local git commits
and live capability state — merged into the system prompt at build time. persona.yaml
stays hand-authored and authoritative for voice/traits; the generated layer supersedes
stale factual claims by prompt ordering.

**Success criteria**

1. New commits / capability drift appear in Nexi's self-narrative within one probe
   cycle (60 s) without manual edits.
2. Zero LLM calls when neither commits nor capability digest changed.
3. LLM or git failures never degrade chat availability or the capability refresh loop.
4. Hand-authored voice/traits are never machine-rewritten.

## 2. Non-goals

- Rewriting `persona.yaml` automatically (rejected during brainstorming).
- Event-driven/webhook commit ingestion (local `git log` chosen).
- Mechanical changelog rendering as the primary narrative (LLM summary chosen).
- Touching xnch or the memory stores.

## 3. Current State (what this builds on)

| Piece | File | Behavior |
|---|---|---|
| Static persona | `nexi/character/persona.yaml` | `load_persona()` reads identity + communication_style |
| Capability overlay | `nexi/character/capability_builder.py` | Drift-gated atomic overlay write; `_GENERATED_KEYS` merge in `prompt_loader.py` |
| Refresh loop | `nexi/main.py:75` `_capability_refresh_loop` | Probes every `probe_interval_s` (60); full overlay write every `capability_refresh_interval_s` (300) |
| Prompt assembly | `nexi/pipeline/context_assembler.py:153` → `prompt_loader.build_system_prompt()` | Per-request system prompt |

## 4. Architecture & Data Flow

```
                    ┌─────────────────────────────────────────┐
                    │  existing _capability_refresh_loop       │
                    │  (main.py:75, every probe_interval_s)    │
                    └──────────────┬──────────────────────────┘
                                   │ after capability refresh
                                   ▼
        ┌────────────── persona_builder.check_and_refresh() ─────────────────┐
        │                                                                    │
        │ 1. collect_commits()   git log --pretty=%s --since=<last_gen>      │
        │    across [".", "nexi", "xnch", "infra"] via subprocess            │
        │ 2. fingerprint = sha256(commit_subjects + capability_digest)       │
        │ 3. if fingerprint != stored → generate_narrative():                │
        │      ModelAdapter structured call                                  │
        │      → {self_narrative, active_projects[], current_stack[]}        │
        │      previous narrative included for continuity                    │
        │ 4. atomic write persona.generated.yaml                             │
        │    {fingerprint, generated_at, narrative…}                         │
        │ 5. emit_event PERSONA_NARRATIVE_UPDATED                            │
        └────────────────────────────┬───────────────────────────────────────┘
                                     ▼
 prompt_loader.build_system_prompt()
   identity traits (persona.yaml)     ← stable voice, first
   ## Self-narrative (generated)      ← second ⇒ factually supersedes stale claims
   capabilities / tools / rules / …   ← existing sections unchanged
```

Key decisions:

- **Drift gate:** `git log` runs each tick (~ms). The LLM fires only when the
  fingerprint changed. `capability_digest` hashes stable content only — tool groups,
  `bridge.active`, healthy/down sets — never timestamps, so probe churn does not
  trigger regeneration.
- **Accumulating window:** commits are collected *since last generation* (stored in
  the overlay), so continuity accrues instead of a rolling window that forgets.
- **Supersede by ordering:** generated section renders immediately after persona
  traits; plus a one-time manual cleanup strips volatile tech enumerations from
  persona.yaml.
- **Failure isolation:** any error keeps the last-good overlay; missing overlay means
  the section is simply absent from the prompt.

## 5. Module Design — `nexi/character/persona_builder.py`

New module mirroring `capability_builder.py` conventions (module docstring listing
sources, dataclasses for results, atomic tmp+rename writes, `logging.getLogger(__name__)`).

```python
@dataclass
class CommitActivity:
    repo: str                      # relative repo path label, e.g. "nexi"
    subjects: list[str] = field(default_factory=list)

@dataclass
class NarrativeResult:
    narrative: dict[str, Any]      # overlay payload (may be last-good on error)
    changed: bool = False
    error: str | None = None
```

Functions:

| Function | Responsibility |
|---|---|
| `collect_commits(repos: list[str \| Path], since_iso: str \| None, max_per_repo: int) -> list[CommitActivity]` | Run `git -C <repo> log --pretty=%s [--since=<iso>] -n <max>` via `subprocess.run`; skip dirs that are not git repos with a warning. Empty output → empty list. Cold start (no stored overlay): `since_iso` is None → most recent N subjects regardless of age. |
| `_capability_digest(caps: dict[str, Any]) -> str` | sha256 over sorted JSON of `{tools: grouped keys+names, bridge.active, bridge.servers(server_id→connected), status.healthy, status.down}`. Timestamps excluded. |
| `compute_fingerprint(activity: list[CommitActivity], caps_digest: str) -> str` | Deterministic sha256 of repo→subjects mapping + digest. |
| `generate_narrative(model_adapter, activity, caps_summary, previous: dict \| None) -> dict` | Build structured prompt (commit subjects grouped by repo, current tool groups, previous narrative); parse model reply into `{self_narrative: str, active_projects: list[str], current_stack: list[str]}`. Raise `PersonaGenerationError` on malformed output. |
| `render_overlay(narrative, fingerprint, generated_at_iso, since_iso) -> str` | YAML body under the AUTO-GENERATED header comment. |
| `write_persona_overlay(path, content) -> bool` | Identical semantics to `capability_builder.write_overlay`: atomic, returns True only on content change. |
| `get_persona_overlay_path() -> Path` | From `settings.persona_generated_path` (env-overridable). |
| `check_and_refresh(model_adapter, capabilities, write=True) -> NarrativeResult` | Orchestrator: read stored fingerprint/since from existing overlay → collect commits since stored `since` (or None) → fingerprint compare → generate on drift → write → audit event. All exceptions caught here except programmer errors; returns `error` field instead. |

Custom exception: `class PersonaGenerationError(Exception)`.

Overlay schema:

```yaml
# AUTO-GENERATED by nexi/character/persona_builder.py — do not edit.
fingerprint: "<sha256>"
generated_at: "2026-08-22T12:00:00Z"
commits_since: "2026-08-15T09:30:00Z"
self_narrative: |
  Over the past week you built the voice UI pipeline and hardened the
  capability refresh loop…
active_projects:
  - voice-ui (feat branch, STT/TTS wiring)
current_stack:
  - vLLM serving Ornith-1.0-35B on gate7
```

## 6. Integration Changes

### 6.1 `nexi/main.py`

In `_capability_refresh_loop`, after each `_refresh_capabilities(...)` succeeds and
when `settings.persona_auto_refresh`:

```python
try:
    result = await persona_builder.check_and_refresh(_model_adapter, caps)
except Exception as exc:
    logger.warning("Persona narrative refresh failed: %s", exc)
```

Writes are not tied to `force_write`: the fingerprint drift gate already prevents
wasted work, so any detected change persists immediately (≤ one probe cycle). The
atomic write itself no-ops when content is unchanged. No new loop/task; lifecycle
unchanged. `/nexi/refresh` additionally calls `check_and_refresh(write=True)`
(dry-run-capable param kept for tests) so manual refreshes also update the narrative.

### 6.2 `nexi/character/prompt_loader.py`

- New constant: `_PERSONA_GENERATED_KEYS = ("self_narrative", "active_projects",
  "current_stack")`.
- `_load_generated_persona_overlay()` — same fallback pattern as capabilities
  (settings path → sibling `persona.generated.yaml`); corrupt YAML logs a warning and
  returns None.
- `load_persona()` returns base merged with generated keys when present (additive;
  existing callers/tests unaffected — new keys only).
- `build_system_prompt()` renders after the trait block, before Capabilities:

```
## Self-narrative (recently evolved)
<self_narrative paragraph>

Active projects:
- …

Current stack (live-derived):
- …
```

Section omitted entirely when no overlay exists.

### 6.3 One-time cleanup — `persona.yaml`

Manual edit accompanying this change (not automated): remove the volatile enumeration
from the "Technically precise" bullet — keep *"Technically precise: you know the XNCH
stack intimately"* and drop "(vLLM Ornith-1.0-35B, pgvector, Kuzu, LiteLLM, Langfuse,
no-k3s two-node layout)". Live-derived `current_stack` now carries that truth.

## 7. Configuration — `nexi/config.py`

```python
# Persona self-narrative auto-refresh
persona_auto_refresh: bool = True
persona_generated_path: str = "~/.xnch/nexi-persona.generated.yaml"
persona_repos: list[str] = [".", "nexi", "xnch", "infra"]
persona_commit_max: int = 40          # max subjects per repo per generation
persona_generation_timeout_s: float = 45.0
```

Env overrides via existing `NEXI_` prefix. Root-repo log covers `docs/`, `scripts/`,
`misc/`; submodules need their own entries (hence the list). `persona_generation_timeout_s`
is applied to the ModelAdapter chat call during narrative generation.

## 8. Error Handling & Safety

| Failure | Behavior |
|---|---|
| Repo missing / not a git repo / git binary absent | Warn, skip repo; others still collected. If all fail → treat as no new commits (fingerprint from digest alone). |
| LLM call fails / timeout / malformed JSON | Keep last-good overlay; `NarrativeResult.error` set; warning logged; retry next tick (natural backoff = probe cadence). |
| Overlay YAML corrupt | Warning; treated as absent (fresh generation next tick). |
| Model adapter unavailable (startup race) | Same as LLM failure; loop retries next tick. |
| Any unexpected exception in loop hook | Caught in main.py wrapper — capability refresh is never blocked. |
| Audit noise | `PERSONA_NARRATIVE_UPDATED` emitted only on actual overlay content change (mirrors `CAPABILITIES_UPDATED`). |

Prompt-size guard: `self_narrative` capped (≤ ~120 words enforced by prompt
instruction + truncation in loader), lists capped at 5 items each.

## 9. Testing Plan

`nexi/tests/test_persona_builder.py` (new; `_make_*` helpers, mocked subprocess and
adapter, autouse isolation fixtures per house style):

- `collect_commits`: parses subjects; skips non-repos; respects `since` and
  `max_per_repo`; empty output tolerated.
- `_capability_digest` / `compute_fingerprint`: stable across identical inputs;
  sensitive to new commit subject; insensitive to `status.checked_at`-style churn.
- `generate_narrative`: valid structured reply parsed; malformed JSON raises
  `PersonaGenerationError`; previous narrative passed through into prompt.
- `check_and_refresh` gating: unchanged fingerprint → no adapter call, no write;
  drift → write + `changed=True`; existing-overlay read of stored fingerprint/since;
  write failure surfaced as `error`.

`nexi/tests/test_prompt_loader.py` (extend):

- Generated persona overlay merges into `load_persona()` result.
- `build_system_prompt()` includes Self-narrative section when overlay present;
  omits section when absent; ordering places it after traits, before Capabilities.
- Corrupt overlay → falls back cleanly, prompt still builds.

`nexi/tests/test_main_loop_integration.py` style smoke (optional): loop hook swallows
persona errors when adapter is broken.

Run: `pytest nexi/tests/test_persona_builder.py nexi/tests/test_prompt_loader.py`.

## 10. Future Work (explicitly out of scope now)

- Human-reviewable rewrite suggestions for slow-changing traits.
- Commit-author/message-quality filtering beyond subject lines.
- Cross-machine repos (gate7-side generation).
