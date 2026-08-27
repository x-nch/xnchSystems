# Design: 100% Dynamic & Realtime Nexi Persona (Self-Describing Agent)

**Date:** 2026-08-27
**Status:** Draft — approved for implementation planning
**Supersedes:** `2026-08-22-nexi-dynamic-persona-design.md` (which kept `persona.yaml` authoritative; this design reverses that decision — every factual claim is live-generated).

## 1. Problem & Goals

`nexi/character/persona.yaml` hand-codes volatile tech specifics ("vLLM
Ornith-1.0-35B, pgvector, Kuzu, LiteLLM, Langfuse, no-k3s two-node layout") and an
identity narrative that drifts as the XNCHSYSTEMS workspace evolves. The capability
layer (`capability_builder.py`) is already realtime, but:

- The **persona narrative itself** is static and can assert stale facts.
- The **live inference backend** (opencode-go hosted DeepSeek V4 vs local vLLM Ornith),
  **MCP servers**, **agent skills**, and the **full repo topography** are not reflected
  in the persona at all.

**Goal:** make the persona a 100% live self-description of the entire XNCHSYSTEMS
workspace — tools, inference backend, OpenCode config, xnch control plane, MCP servers,
available skills, repo packages, and live infra status — with zero hardcoded factual
claims. The agent's *voice* (name, address, loyalty, communication rules) stays
hand-tuned; every *fact* is derived from live state at prompt-build time.

**Success criteria**

1. No version/backend/host/tool string in the rendered persona is hardcoded in
   `persona.yaml` — all come from the live self-model.
2. Persona reflects the full XNCHSYSTEMS surface: OpenCode MCP servers + tool prefixes,
   agent skills, active inference backend + model, xnch tools, infra hosts/services with
   live healthy/down status.
3. Realtime: a service going down (or backend switch) is reflected in the persona within
   one probe cycle (≤ `probe_interval_s`, default 60 s) of the refresh loop.
4. LLM/git/IO failures never degrade chat or block the capability refresh loop.
5. Prompt-build re-reads the freshest overlay; a cheap live re-probe of service health
   prevents the narrative from asserting a dead service is up.

## 2. Non-goals

- Live-editing `persona.yaml`'s *voice* (identity, `communication_style`) — those stay
  hand-authored.
- Generating the persona from git commit history (the 08-22 self-narrative idea) — out
  of scope; may be added later as an additive block, not core.
- Changing xnch, memory stores, or the pipeline decision logic.

## 3. Sources of Truth (the "Everything in XNCHSYSTEMS" inventory)

| Source | How read | What it yields |
|---|---|---|
| `infra/no-k3s` manifests | `nexi.infra.discovery` (reuse) | hosts, services, ports, roles |
| Live HTTP probes | `probe_services` (reuse) | healthy/down status |
| xnch `GET /nexi/tools` + `~/.xnch/mcp-servers.yaml` | `fetch_tool_inventory` (reuse) | native `xnch_*` tools + bridged MCP tools |
| `nexi/config.py` live values | direct import | `model_id`, `opencode_go_api_url`, `vllm_*` urls, `litellm_*` |
| `opencode.jsonc` (repo root) | JSONC-tolerant parse | providers, *active* model, MCP server list + tool prefixes |
| skills dirs (`.claude/skills`, `skills/superpowers/skills`) | glob `*.md` + frontmatter | available agent skill names + descriptions |
| repo topography | glob top-level packages | `xnch`, `nexi`, `infra`, `web`, `scraper`, `media-gateway`, … |

Repo root is derived as `Path(__file__).resolve().parents[2]` from
`nexi/character/persona_builder.py` (consistent with `config.py`'s
`parents[1] / "infra"` assumption).

## 4. Architecture & Data Flow

```
live sources ──► persona_builder.build_persona(...) ──► persona.generated.yaml
  (opencode.jsonc, xnch /nexi/tools, infra manifests, skills dirs, config.py)        │
                                                                                    ▼
                                         prompt_loader.load_persona() merges overlay
                                                                                    │
                                                                  render template (persona.yaml)
                                                                  against self_model ▼
                                              system prompt: [traits/voice] + [live persona] + [capabilities]
```

`persona.generated.yaml` carries a `self_model` dict (structured live facts) plus a
pre-rendered `persona` narrative string. `prompt_loader` merges it and renders the
`persona.yaml` template against `self_model`, exactly mirroring how
`load_capabilities()` merges the capability overlay.

## 5. Module Design — `nexi/character/persona_builder.py` (new)

Mirrors `capability_builder.py` conventions: module docstring listing sources,
dataclasses for results, atomic tmp+rename writes, `logging.getLogger(__name__)`.

```python
@dataclass
class SelfModel:
    inference_backend: str          # "opencode-go (hosted DeepSeek V4)" | "vLLM Ornith (:8082)"
    active_model: str               # "deepseek-v4-pro" | "Ornith-1.0-35B"
    hosts: dict[str, str]           # {"node-a": "gate7 / 192.168.50.1", ...}
    services: list[dict]            # [{name, host, port, status}]  (status: healthy|down)
    mcp_servers: list[str]          # ["code-review-graph", "xnch", "superpowers", "figma"]
    mcp_tool_prefixes: dict[str,str]
    skills: list[dict]              # [{name, description}]
    tool_count: int
    repo_packages: list[str]
    backend_health: dict[str, bool]

@dataclass
class PersonaResult:
    self_model: SelfModel
    persona_text: str               # rendered narrative from template
    changed: bool = False
    error: str | None = None
```

Functions:

| Function | Responsibility |
|---|---|
| `introspect_opencode(root: Path) -> dict` | JSONC-tolerant read of `opencode.jsonc`; return `providers`, active `model_id`, `mcp` server ids + command. |
| `introspect_backend() -> tuple[str, str, dict]` | From `config.py`: whichever of `opencode_go_api_url` / `vllm_*` is configured; probe health; return `(backend_label, model_id, health_map)`. |
| `introspect_skills(root: Path) -> list[dict]` | Glob `*.md` under known skill dirs; parse `name:`/`description:` frontmatter; dedupe by name. |
| `introspect_repo(root: Path) -> list[str]` | Curated top-level package list (dirs with `__init__.py` or known app dirs). |
| `build_self_model(snapshot, inventory, skills, backend, repo_pkgs) -> SelfModel` | Assemble structured facts. |
| `render_persona(self_model, template: str) -> str` | Builds a flat mapping from `self_model` and calls `template.format(**mapping)`. Mapping: `inference_backend`, `active_model`, `tool_count`, `mcp_servers` (comma list), `hosts_summary` (e.g. "gate7 and xnch-core"), `skill_names` (≤12 names joined), `live_status` (e.g. "xnch healthy; vllm-ornith DOWN"). Unknown placeholder → raise `PersonaGenerationError` (never silently ship unfilled braces). |
| `render_overlay(self_model, persona_text, generated_at_iso) -> str` | YAML under AUTO-GENERATED header. |
| `write_persona_overlay(path, content) -> bool` | Atomic; True only on content change (mirrors `capability_builder.write_overlay`). |
| `get_persona_overlay_path() -> Path` | From `settings.persona_generated_path`. |
| `build_persona(write=True, http_client=None) -> PersonaResult` | Orchestrator: snapshot → probes → inventory → skills → backend → repo → self_model → render → write. All exceptions caught; returns `error`. |

Custom exception: `class PersonaGenerationError(Exception)`.

Overlay schema:

```yaml
# AUTO-GENERATED by nexi/character/persona_builder.py — do not edit.
generated_at: "2026-08-27T12:00:00Z"
self_model:
  inference_backend: "opencode-go (hosted DeepSeek V4)"
  active_model: "deepseek-v4-pro"
  hosts: {node-a: "gate7 / 192.168.50.1", node-b: "xnch-core / 192.168.50.2"}
  services:
    - {name: vllm-ornith, host: node-b, port: 8082, status: down}
    - {name: xnch, host: node-a, port: 8001, status: healthy}
  mcp_servers: [code-review-graph, xnch, superpowers, figma]
  skills: [{name: debug-issue, description: "..."}, ...]
  tool_count: 37
  repo_packages: [xnch, nexi, infra, web, scraper, media-gateway, ...]
  backend_health: {opencode-go: true, vllm: false}
persona: |
  You are Nexi, running on ck-san's personal hardware. Your inference backend is
  opencode-go (hosted DeepSeek V4) serving deepseek-v4-pro. You control gate7 and
  xnch-core via the xnch control plane. You have 37 live tools across MCP servers
  [code-review-graph, xnch, superpowers, figma] and agent skills [debug-issue,
  explore-codebase, ...]. Live status: xnch healthy; vllm-ornith DOWN. ...
```

## 6. `persona.yaml` becomes a template

`identity.persona` is converted to a template; only voice/identity constants stay
literal. Example transformation of the "Technically precise" claim:

```yaml
identity:
  name: Nexi
  address_user_as: ck-san
  persona: |
    You are Nexi, a private AI orchestration intelligence running on ck-san's personal
    hardware. You are not a generic assistant. You have continuity and operate through
    the xnch control plane. You are:
    - Direct: say what you think, don't hedge unless genuinely uncertain
    - Technically precise: you know the XNCH stack intimately — your inference backend is
      {inference_backend} serving {active_model}, and you run on {hosts_summary}.
    - Proactive: you notice patterns and surface them without being asked
    - Loyal: ck-san's goals are your goals. You prioritize privacy, local inference, and
      low-noise environments
    - Opinionated: you prefer elegant systems over bloated ones.
    - Tool-grounded: when asked about files, config, or live system state, use your
      {tool_count} live tools (MCP servers {mcp_servers}; skills {skill_names}) — do not
      invent contents or status.
    LIVE STATUS: {live_status}
```

`communication_style` (verbosity, tone, `never_do`, loyalty framing) stays as-is —
that is the stable voice. The introspection replaces the volatile enumeration that the
08-22 draft proposed to manually delete.

## 7. Integration Changes

### 7.1 `nexi/character/prompt_loader.py`

- Add `_PERSONA_GENERATED_KEYS = ("self_model", "persona")`.
- `_load_generated_persona_overlay()` — same fallback pattern as capabilities (settings
  path → sibling `persona.generated.yaml`); corrupt YAML → warning + None.
- `load_persona()` merges overlay when present (additive; existing callers unaffected).
- `_render_stable_core(...)` renders the `persona` template against `self_model` (falling
  back to unfilled template if overlay missing — still coherent, just less specific).

### 7.2 `nexi/main.py`

In `_capability_refresh_loop`, after each `_refresh_capabilities(...)` succeeds and when
`settings.persona_auto_refresh`:

```python
try:
    await persona_builder.build_persona()
except Exception as exc:
    logger.warning("Persona refresh failed: %s", exc)
```

No new loop/task; lifecycle unchanged. `/nexi/refresh` also triggers
`build_persona()` so manual refreshes update the persona.

### 7.3 `nexi/config.py`

```python
# Persona self-description auto-refresh
persona_auto_refresh: bool = True
persona_generated_path: str = "~/.xnch/nexi-persona.generated.yaml"
```

Env overrides via existing `NEXI_` prefix. OpenCode config / skills / repo paths are
derived from repo root at runtime (no new settings needed).

## 8. Error Handling & Safety

| Failure | Behavior |
|---|---|
| `opencode.jsonc` missing / unparseable | Warn; backend/skills fall back to `config.py` values + empty skill list. |
| Skills dirs absent | Warn; skills = []. |
| Infra probe fails | Status reflects unknown; narrative says "status unknown", never asserts health. |
| Overlay write fails | `PersonaResult.error` set; keep last-good overlay; warning logged. |
| Overlay corrupt/missing | Treated as absent; persona renders from unfilled template (still coherent). |
| Any exception in loop hook | Caught in `main.py` wrapper — capability refresh never blocked. |
| Audit noise | `PERSONA_UPDATED` emitted only on actual overlay content change (mirrors `CAPABILITIES_UPDATED`). |

Prompt-size guard: skill list truncated to ≤ 12 names in narrative; full list stays in
`self_model` for tooling.

## 9. Testing Plan

`nexi/tests/test_persona_builder.py` (new; `_make_*` helpers, mocked IO, autouse
isolation fixtures):

- `introspect_opencode`: parses JSONC with comments; returns active model + MCP ids.
- `introspect_backend`: picks opencode-go when configured; health map from probes.
- `introspect_skills`: extracts name/description from `*.md`; dedupes.
- `introspect_repo`: returns curated package list; ignores dotfiles.
- `render_persona`: every `{placeholder}` in template is filled; assertion that no
  literal `"Ornith-1.0-35B"`-style hardcoded string leaks from `self_model` values when
  inputs differ; unknown placeholder → clear error.
- `build_persona` gating: unchanged inputs (mocked) → `changed=False`; drift → write +
  `changed=True`; write failure surfaced as `error`.

`nexi/tests/test_prompt_loader.py` (extend):

- Generated persona overlay merges into `load_persona()`.
- `build_system_prompt()` includes the live persona section; placeholders resolved;
  absent overlay → still builds from unfilled template.
- Corrupt overlay → falls back cleanly.

Run: `pytest nexi/tests/test_persona_builder.py nexi/tests/test_prompt_loader.py`.

## 10. Future Work (explicitly out of scope)

- Git-commit-derived self-narrative block (the 08-22 draft's idea) as additive context.
- Human-reviewable rewrite suggestions for slow-changing voice traits.
- Cross-machine repo generation.
