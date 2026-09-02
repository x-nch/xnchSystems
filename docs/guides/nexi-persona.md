# Nexi persona — dynamic & realtime (2026-08-27)

Nexi's persona is 100% dynamic: `persona.yaml`, `capabilities.yaml`, and
`identity_facts.yaml` under `nexi/character/` are inputs; the rendered overlay is
written to `NEXI_PERSONA_GENERATED_PATH` (`~/.xnch/nexi-persona.generated.yaml` by
default) and reloaded at runtime (`f84a8e9`). Model selection is per-task via the
OpenCode Go catalog (`NEXI_OPENCODE_GO_MODELS` override — see
[env-vars](../reference/env-vars.md)). Prompt construction uses stable-prefix
segmentation so the API can cache the unchanged prefix (`c375d47`).

## Manual refresh

Run: `~/venvs/xnch/bin/python -m nexi.character.refresh --verbose`
Expected: prints overlay change status; exit 0. (The xnch venv is used so
`prometheus_client` resolves — `25e937c`.)

Spec: [dynamic nexi persona design](../superpowers/specs/2026-08-27-dynamic-nexi-persona-design.md)
