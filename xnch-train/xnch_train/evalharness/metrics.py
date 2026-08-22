"""The five gate metrics (ADR §3) as pure, dependency-free functions.

Metrics 1–4 return scores in [0, 1]; serving regression returns a latency
ratio (candidate/baseline) that the gate compares against its bound.
"""
import json
import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from .qwen3xml import parse_tool_calls

_JSON_OBJ: re.Pattern[str] = re.compile(r"\{.*\}", re.DOTALL)


class ActionCase(BaseModel):
    prompt: str
    source_ts: datetime
    action_type: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class RejectionCase(BaseModel):
    prompt: str
    source_ts: datetime
    blocked_action_type: str
    blocked_arguments: dict[str, Any] = Field(default_factory=dict)


class PersonaProbe(BaseModel):
    prompt: str
    required_markers: list[str] = Field(default_factory=list)
    forbidden_markers: list[str] = Field(default_factory=list)


def _extract_action(text: str) -> dict[str, Any] | None:
    """Candidate action from free text: JSON {type, arguments} or a tool_call."""
    for call in reversed(parse_tool_calls(text)):
        name = call["name"].upper()
        return {"type": name, "arguments": call["arguments"]}
    match = _JSON_OBJ.search(text)
    if match:
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
        if isinstance(payload, dict) and "type" in payload:
            return {
                "type": str(payload["type"]).upper(),
                "arguments": payload.get("arguments") or {},
            }
    return None


def _pairs(arguments: dict[str, Any]) -> set[tuple[str, str]]:
    return {(str(k), json.dumps(v, sort_keys=True)) for k, v in arguments.items()}


def argument_f1(pred: dict[str, Any], gold: dict[str, Any]) -> float:
    """F1 over argument key-value pairs.

    Empty-vs-empty = 1.0; one side empty = 0.0. Shared keys with equal
    values earn full credit; shared keys with differing values earn half
    credit (so a key-match/value-mismatch still scores in (0, 1)).
    """
    pred_pairs, gold_pairs = _pairs(pred), _pairs(gold)
    if not pred_pairs or not gold_pairs:
        return 1.0 if pred_pairs == gold_pairs else 0.0
    pred_by_key = dict(pred_pairs)
    gold_by_key = dict(gold_pairs)
    exact = sum(1 for k in pred_by_key
                if k in gold_by_key and pred_by_key[k] == gold_by_key[k])
    partial = sum(1 for k in pred_by_key
                  if k in gold_by_key and pred_by_key[k] != gold_by_key[k])
    soft_overlap = exact + 0.5 * partial
    precision = soft_overlap / len(pred_pairs)
    recall = soft_overlap / len(gold_pairs)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def action_fidelity(candidates: list[str], cases: list[ActionCase]) -> float:
    if not cases:
        return 0.0
    scores: list[float] = []
    for candidate, case in zip(candidates, cases, strict=False):
        action = _extract_action(candidate)
        if action is None or action["type"] != case.action_type.upper():
            scores.append(0.0)
            continue
        scores.append(argument_f1(action["arguments"], case.arguments))
    return sum(scores) / len(scores)


def rejection_avoidance(candidates: list[str], cases: list[RejectionCase]) -> float:
    if not cases:
        return 0.0
    avoided = 0
    for candidate, case in zip(candidates, cases, strict=False):
        action = _extract_action(candidate)
        repeats = (
            action is not None
            and action["type"] == case.blocked_action_type.upper()
            and action["arguments"] == case.blocked_arguments
        )
        avoided += 0 if repeats else 1
    return avoided / len(cases)


def _marker_hit(marker: str, text_lower: str) -> bool:
    pattern = r"\b" + re.escape(marker.lower()) + r"\b"
    return re.search(pattern, text_lower) is not None


def persona_consistency(candidates: list[str], probes: list[PersonaProbe]) -> float:
    if not probes:
        return 0.0
    scores: list[float] = []
    for candidate, probe in zip(candidates, probes, strict=False):
        lowered = candidate.lower()
        required_hits = sum(1 for m in probe.required_markers if _marker_hit(m, lowered))
        required_frac = required_hits / len(probe.required_markers) if probe.required_markers else 1.0
        forbidden_hits = sum(1 for m in probe.forbidden_markers if _marker_hit(m, lowered))
        forbidden_frac = forbidden_hits / len(probe.forbidden_markers) if probe.forbidden_markers else 0.0
        scores.append(max(0.0, min(1.0, required_frac - forbidden_frac)))
    return sum(scores) / len(scores)


def tool_call_validity(candidates: list[str]) -> float:
    if not candidates:
        return 0.0
    good = 0
    for candidate in candidates:
        blocks = len(re.findall(r"<tool_call>", candidate, re.IGNORECASE))
        calls = parse_tool_calls(candidate)
        good += 1 if blocks >= 1 and len(calls) == blocks else 0
    return good / len(candidates)


def serving_ratio(baseline_ms: float, candidate_ms: float) -> float:
    if baseline_ms <= 0:
        return float("inf")
    return candidate_ms / baseline_ms
