"""Incumbent-only baseline runner — captures the five gate numbers.

Phase 0 exit criterion: a baseline eval report exists for the incumbent
checkpoint under harness suite v1 (ADR §3, Phase 0 row).
"""
import statistics
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from .client import ModelClient
from .metrics import action_fidelity, persona_consistency, rejection_avoidance, tool_call_validity
from .suites import EvalSuite


class BaselineReport(BaseModel):
    checkpoint_id: str
    suite_version: str
    generated_at: datetime
    action_fidelity: float
    rejection_avoidance: float
    persona_consistency: float
    tool_call_validity: float
    latency_p50_ms: float
    latency_p95_ms: float
    meta: dict[str, Any] = Field(default_factory=dict)


async def run_baseline(
    client: ModelClient, suite: EvalSuite, checkpoint_id: str = "incumbent"
) -> BaselineReport:
    fidelity_replies = [await client.complete(c.prompt) for c in suite.fidelity]
    rejection_replies = [await client.complete(c.prompt) for c in suite.rejection]
    persona_replies = [await client.complete(p.prompt) for p in suite.persona]
    toolset_replies = [await client.complete(p) for p in suite.toolset_prompts]
    bench_replies = [await client.complete(p) for p in suite.bench_prompts]

    latencies = sorted(r.latency_ms for r in bench_replies) or [0.0]
    p50 = statistics.median(latencies)
    p95_index = max(0, min(len(latencies) - 1, round(0.95 * (len(latencies) - 1))))
    p95 = latencies[p95_index]

    return BaselineReport(
        checkpoint_id=checkpoint_id,
        suite_version=suite.suite_version,
        generated_at=datetime.now(tz=UTC),
        action_fidelity=action_fidelity([r.text for r in fidelity_replies], suite.fidelity),
        rejection_avoidance=rejection_avoidance([r.text for r in rejection_replies], suite.rejection),
        persona_consistency=persona_consistency([r.text for r in persona_replies], suite.persona),
        tool_call_validity=tool_call_validity([r.text for r in toolset_replies]),
        latency_p50_ms=p50,
        latency_p95_ms=p95,
        meta={"samples": {"fidelity": len(suite.fidelity), "rejection": len(suite.rejection),
                          "persona": len(suite.persona), "toolset": len(suite.toolset_prompts),
                          "bench": len(suite.bench_prompts)}},
    )
