#!/usr/bin/env python3
"""Free model selector CLI.

Discovers free models (OpenCode Go + OpenRouter), enriches with ELO/manual
tiers, probes latency and writes rankings to Redis + a JSON audit dump.

Usage:
    python scripts/model_selector.py run
    python scripts/model_selector.py probe
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import httpx
import typer

from nexi.adapters.model_selector import (
    discover_opencode,
    discover_openrouter,
    dump_rankings_json,
    fetch_elo,
    load_config,
    probe_latency,
    rank_models,
    read_rankings,
    redis_client_from,
    write_rankings,
)
from nexi.config import settings

logger = logging.getLogger(__name__)

app = typer.Typer(help="Discover, benchmark and rank free LLM models.")
_RANKINGS_PATH = Path(__file__).resolve().parents[1] / "data" / "model-rankings.json"


async def _discover_safe(coro, source: str) -> list[dict]:
    try:
        return await coro
    except Exception as exc:
        logger.warning("discovery from %s failed: %s", source, exc)
        return []


async def _collect() -> tuple[list[dict], dict[str, float], dict[str, str]]:
    cfg = load_config(settings.model_selector_config_path)
    opencode_headers = {}
    if settings.opencode_go_api_key:
        opencode_headers["Authorization"] = f"Bearer {settings.opencode_go_api_key}"
    # Separate clients: the OpenCode credential must never reach third parties.
    async with (
        httpx.AsyncClient(headers=opencode_headers, timeout=30.0) as oc_client,
        httpx.AsyncClient(timeout=30.0) as client,
    ):
        opencode = await _discover_safe(
            discover_opencode(oc_client, settings.opencode_go_api_url), "opencode"
        )
        or_models = await _discover_safe(
            discover_openrouter(client, settings.openrouter_api_url), "openrouter"
        )
        elo = await fetch_elo(client)
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
                c,
                e["provider"],
                e["model_id"],
                base,
                key,
                cfg.probe.prompt,
                cfg.probe.timeout_s,
                cfg.probe.runs,
            )
            for e, base, key in targets
        ]
    for entry, res in zip(entries, results):
        if res["ok"]:
            entry["latency_ms"] = res["total_ms"] or 0
    return entries


@app.command()
def run():
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
    ranked = read_rankings(client, cfg.redis.rankings_key, cfg.redis.ttl_s)
    if not ranked:
        typer.echo("No cached rankings; run `model_selector.py run` first.", err=True)
        raise typer.Exit(1)
    entries = [
        {
            "provider": r["provider"],
            "model_id": r["model_id"],
            "latency_ms": r.get("latency_ms", 0),
            "context_window": int(r.get("context_window") or 64_000),
        }
        for r in ranked
    ]
    elo = {r["model_id"]: r["elo"] for r in ranked if r.get("elo") is not None}
    refreshed = asyncio.run(_probe_all(entries, cfg))
    ranked = rank_models(refreshed, elo, dict(cfg.manual_tiers), weights=cfg.weights)
    write_rankings(client, ranked, cfg.redis.rankings_key, cfg.redis.ttl_s)
    dump_rankings_json(ranked, _RANKINGS_PATH)
    typer.echo(f"re-probed {len(refreshed)} models, rankings updated")


if __name__ == "__main__":
    app()
