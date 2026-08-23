"""Langfuse extractor — zero new instrumentation, reads existing traces.

Verdicts are recovered from policy-engine generations whose prompt/response
were logged by xnch's trace_llm_call (routes/verdict.py): prompt JSON carries
{action, actor, context}; completion JSON carries the authoritative verdict.
"""
import base64
import json
import logging
from datetime import datetime
from typing import Any

import httpx

from ..models.records import RecordSource, TrainingRecord, VerdictKind

logger = logging.getLogger(__name__)

_POLICY_MODEL = "policy-engine"
_ALLOWED_VERDICTS = {"ALLOW", "BLOCK", "MODIFY"}


class LangfuseExtractor:
    def __init__(
        self, host: str, public_key: str, secret_key: str, page_size: int = 100
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=host.rstrip("/"),
            timeout=30.0,
            headers={
                "Authorization": "Basic "
                + base64.b64encode(f"{public_key}:{secret_key}".encode()).decode(),
            },
        )
        self._page_size = page_size

    async def aclose(self) -> None:
        await self._client.aclose()

    async def fetch_traces_page(self, page: int) -> list[dict[str, Any]]:
        resp = await self._client.get(
            "/api/public/traces",
            params={"page": page, "limit": self._page_size},
        )
        resp.raise_for_status()
        return list(resp.json().get("data", []))

    async def fetch_observations(self, trace_id: str) -> list[dict[str, Any]]:
        resp = await self._client.get(
            "/api/public/observations", params={"traceId": trace_id}
        )
        resp.raise_for_status()
        return list(resp.json().get("data", []))

    @staticmethod
    def verdict_record_from_observation(obs: dict[str, Any]) -> TrainingRecord | None:
        if obs.get("name") != "llm-call" or obs.get("model") != _POLICY_MODEL:
            return None
        try:
            request = json.loads(str(obs.get("prompt", "")))
            response = json.loads(str(obs.get("completion", "")))
        except json.JSONDecodeError:
            return None
        if not isinstance(request, dict) or not isinstance(response, dict):
            return None
        raw_verdict = str(response.get("verdict", "")).upper()
        if "action" not in request or raw_verdict not in _ALLOWED_VERDICTS:
            return None
        mapped = VerdictKind.APPROVE if raw_verdict == "ALLOW" else VerdictKind(raw_verdict)
        ts_raw = str(obs.get("timestamp", ""))
        try:
            ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
        except ValueError:
            logger.warning("observation %s has bad timestamp %r", obs.get("id"), ts_raw)
            ts = datetime.now(tz=None)
        return TrainingRecord(
            trace_id=str(obs.get("traceId") or obs.get("id", "")),
            ts=ts,
            source=RecordSource.VERDICT,
            input_context=json.dumps(request.get("action", {})),
            output=json.dumps(response),
            verdict=mapped,
        )

    async def extract_verdicts(self, max_traces: int = 1000) -> list[TrainingRecord]:
        records: list[TrainingRecord] = []
        page = 1
        seen = 0
        while seen < max_traces:
            traces = await self.fetch_traces_page(page)
            if not traces:
                break
            for trace in traces:
                seen += 1
                if seen > max_traces:
                    break
                for obs in await self.fetch_observations(str(trace.get("id", ""))):
                    record = self.verdict_record_from_observation(obs)
                    if record is not None:
                        records.append(record)
            page += 1
        logger.info("extracted %d verdict records from %d traces", len(records), seen)
        return records
