"""Langfuse extractor — verdict preference pairs from policy-engine trace I/O."""
import json
from typing import Any

import pytest

from xnch_train.extract.langfuse_extract import LangfuseExtractor
from xnch_train.models.records import RecordSource, VerdictKind

HOST = "http://lf.test"


def _policy_generation(verdict: str = "BLOCK") -> dict[str, Any]:
    return {
        "id": "gen-1",
        "traceId": "tr-1",
        "name": "llm-call",
        "model": "policy-engine",
        "prompt": json.dumps({"action": {"type": "DEPLOY"}, "actor": {}, "context": {}}),
        "completion": json.dumps({"verdict": verdict, "reason": "rule-x"}),
        "timestamp": "2026-08-01T00:00:00Z",
    }


def _unrelated_observation() -> dict[str, Any]:
    return {"id": "obs-9", "traceId": "tr-1", "name": "tool-span",
            "model": "ornith", "prompt": "hi", "completion": "ho"}


async def test_verdict_record_from_observation_maps_allow_to_approve() -> None:
    rec = LangfuseExtractor.verdict_record_from_observation(_policy_generation("ALLOW"))
    assert rec is not None
    assert rec.source is RecordSource.VERDICT
    assert rec.verdict is VerdictKind.APPROVE
    assert rec.trace_id == "tr-1"


async def test_verdict_record_keeps_block_and_modify() -> None:
    for raw, expected in (("BLOCK", VerdictKind.BLOCK), ("MODIFY", VerdictKind.MODIFY)):
        rec = LangfuseExtractor.verdict_record_from_observation(_policy_generation(raw))
        assert rec is not None
        assert rec.verdict is expected


async def test_non_policy_observations_return_none() -> None:
    obs = _unrelated_observation()
    assert LangfuseExtractor.verdict_record_from_observation(obs) is None


async def test_malformed_payloads_return_none() -> None:
    bad = {"name": "llm-call", "model": "policy-engine",
           "prompt": "not json", "completion": "also not"}
    assert LangfuseExtractor.verdict_record_from_observation(bad) is None


async def test_scalar_and_array_payloads_return_none() -> None:
    base = {"name": "llm-call", "model": "policy-engine"}
    for prompt, completion in (("5", '{"verdict": "BLOCK"}'),
                               ('{"action": {}}', "null"),
                               ('{"action": {}}', '["BLOCK"]')):
        obs = {**base, "prompt": prompt, "completion": completion}
        assert LangfuseExtractor.verdict_record_from_observation(obs) is None


async def test_extract_verdicts_paginates_and_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    ex = LangfuseExtractor(HOST, "pk", "sk", page_size=1)

    async def fake_page(page: int) -> list[dict[str, Any]]:
        if page <= 2:
            return [{"id": f"tr-{page}"}]
        return []

    async def fake_obs(trace_id: str) -> list[dict[str, Any]]:
        if trace_id == "tr-1":
            return [_policy_generation("ALLOW"), _unrelated_observation()]
        return []

    monkeypatch.setattr(ex, "fetch_traces_page", fake_page)
    monkeypatch.setattr(ex, "fetch_observations", fake_obs)
    records = await ex.extract_verdicts()
    assert [r.trace_id for r in records] == ["tr-1"]
    assert records[0].verdict is VerdictKind.APPROVE
