#!/usr/bin/env python3
"""Free model selector CLI.

Discovers free models (OpenCode Go + OpenRouter), enriches with ELO/manual
tiers, probes latency and writes rankings to Redis + a JSON audit dump.

Usage:
    python scripts/model_selector.py run
    python scripts/model_selector.py probe
    python scripts/model_selector.py show [--intent DECISION]
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import httpx
import typer

from nexi.adapters import model_router as mr
from nexi.adapters.model_selector import (
    load_config,
    rank_models,
    redis_client_from,
    write_rankings,
    dump_rankings_json,
    discover_opencode,
    discover_openrouter,
    fetch_elo,
    probe_latency,
)
from nexi.config import settings

app = typer.Typer(help="Discover, benchmark and rank free LLM models.")
_RANKINGS_PATH = Path(__file__).resolve().parents[1] / "data" / "model-rankings.json"


async def _collect() -> tuple[list[dict], dict[str, float], dict[str, str]]:
    cfg = load_config(settings.model_selector_config_path)
    base = settings.opencode_go_api_url
    headers = {}
    if settings.opencode_go_api_key:
        headers["Authorization"] = f"Bearer {settings.opencode_go_api_key}"
    async with httpx.AsyncClient(headers=headers, timeout=30.0) as c:
        opencode = await discover_opencode(c, base)
        or_models = await discover_openrouter(c, settings.openrouter_api_url)
        elo = await fetch_elo(c)
    tiers: dict[str, str] = dict(cfg.manual_tiers)
    return opencode + or_models, elo, tiers


async def _probe_all(entries: list[dict], cfg) -> list[dict]:
    targets: list[tuple[dict, str, str]] = []
    for e in entries:
        if e["provider"] == "opencode":
            targets.append((e, settings.opencode_go_api_url, settings.opencode_go_api_key))
        else:
            targets.append((e, settings.openrouter_api_url, settings.openrouter_api_key))
    async with httpx.AsyncClient(timeout=cfg.probe.timeout_s) as c:
        results = [
            await probe_latency(
                c, e["provider"], e["model_id"], base, key, cfg.probe.prompt,
                cfg.probe.timeout_s, cfg.probe.runs,
            )
            for e, base, key in targets
        ]
    for entry, res in zip(entries, results):
        if res["ok"]:
            entry["latency_ms"] = res["total_ms"] or 0
    return entries


@app.command()
def run(force: bool = typer.Option(False, "--force")):
    """Discover + probe + rank + store."""
    cfg = load_config()
    models, elo, tiers = asyncio.run(_collect())
    entries = asyncio.run(_probe_all(models, cfg)) if models else []
    ranked = rank_models(entries, elo, tiers, weights=cfg.weights)
    client = redis_client_from(cfg)
    write_rankings(client, ranked, cfg.redis.rankings_key, cfg.redis.ttl_s)
    dump_rankings_json(ranked, _RANKINGS_PATH)
    typer.echo(f"discovered={len(models)} ranked={len(ranked)} key={cfg.redis.rankings_key}")


@app.command()
def probe():
    """Re-benchmark known ranked models on latency."""
    cfg = load_config()
    client = redis_client_from(cfg)
    raw = client.get(cfg.redis.rankings_key)
    if not raw:
        typer.echo("No cached rankings; run `model_selector.py run` first.", err=True)
        raise typer.Exit(1)
    ranked = json.loads(raw)
    entries = [
        {"provider": r["provider"], "model_id": r["model_id"], "latency_ms": r.get("latency_ms", 0)}
        for r in ranked
    ]
    refreshed = asyncio.run(_probe_all([{**e, "context_window": 64_000} for e in entries], cfg))
    ranked = rank_models(refreshed, {r.get("elo") and r["model_id"]: r["elo"] for r in ranked if r.get("elo")}, {}, weights=cfg.weights)
    write_rankings(client, ranked, cfg.redis.rankings_key, cfg.redis.ttl_s)
    typer.echo(f"re-probed {len(refreshed)} models, rankings updated")


if __name__ == "__main__":
    app()