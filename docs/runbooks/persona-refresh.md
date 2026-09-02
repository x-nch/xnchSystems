# Runbook — persona refresh timer (node-a)

Systemd timer deploys the nexi persona/capability refresh (`f6d7d9d`):
`infra/no-k3s/node-a/systemd/nexi-persona-refresh.timer` (+ service unit alongside).

## Deploy

Run: `sudo systemctl daemon-reload && sudo systemctl enable --now nexi-persona-refresh.timer`
Expected: `systemctl status nexi-persona-refresh.timer` shows active (waiting).

## Validate

Run: `systemctl list-timers nexi-persona-refresh.timer && journalctl -u nexi-persona-refresh.service -n 20`
Expected: timer listed with next trigger; service log shows the refresh completing with exit 0.

## Rollback

Run: `sudo systemctl disable --now nexi-persona-refresh.timer`
Expected: timer removed from `list-timers`; manual refresh remains available
(see [persona guide](../guides/nexi-persona.md)).

Footgun: the service must run under the xnch venv — if you see
`ModuleNotFoundError: prometheus_client`, the unit is using the wrong interpreter (`25e937c`).
