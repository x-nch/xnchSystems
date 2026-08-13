"""Minimal Langfuse ingestion client — mirrors xnch/observability.

Keeps the gateway on the same observability layer as the rest of the stack:
LLM calls and ComfyUI job lifecycles emit to Langfuse as spans under one
trace id per media job. No-op (fire-and-forget, error-swallowing) when the
LANGFUSE_* env vars are absent, so the gateway never blocks on telemetry.
"""
import base64
import hashlib
import logging
import time
from typing import Any

import httpx

from .config import Settings

logger = logging.getLogger(__name__)


class LangfuseClient:
    def __init__(self, settings: Settings) -> None:
        self._public_key = settings.langfuse_public_key
        self._secret_key = settings.langfuse_secret_key
        self._host = settings.langfuse_host.rstrip("/")
        self._client = httpx.AsyncClient(base_url=self._host, timeout=5.0)

    @property
    def enabled(self) -> bool:
        return bool(self._public_key and self._secret_key)

    async def aclose(self) -> None:
        await self._client.aclose()

    def _headers(self) -> dict[str, str]:
        raw = f"{self._public_key}:{self._secret_key}"
        return {
            "Authorization": f"Basic {base64.b64encode(raw.encode()).decode()}",
            "Content-Type": "application/json",
        }

    async def _ingest(self, body: dict[str, Any]) -> None:
        if not self.enabled:
            return
        try:
            resp = await self._client.post(
                "/api/public/ingestion",
                headers=self._headers(),
                json={"batch": [{"type": "generation-create", "body": body}]},
            )
            resp.raise_for_status()
        except Exception:
            logger.debug("langfuse ingest failed", exc_info=True)

    async def trace_llm_call(
        self,
        prompt: str,
        response: str,
        model: str,
        latency_ms: int,
        tokens_used: int,
        trace_id: str = "",
    ) -> None:
        generation_id = hashlib.sha256(
            f"{trace_id}{time.time_ns()}".encode()
        ).hexdigest()[:16]
        await self._ingest(
            {
                "id": generation_id,
                "traceId": trace_id or generation_id,
                "name": "llm-call",
                "model": model,
                "usage": {
                    "input": len(prompt.split()),
                    "output": len(response.split()),
                    "total": len(prompt.split()) + len(response.split()),
                },
                "prompt": prompt,
                "completion": response,
                "latency": latency_ms,
            }
        )

    async def emit_job_span(self, job: Any) -> None:
        """Emit a media-job lifecycle span (queued/running/done/failed)."""
        generation_id = hashlib.sha256(
            f"job-{job.job_id}-{time.time_ns()}".encode()
        ).hexdigest()[:16]
        await self._ingest(
            {
                "id": generation_id,
                "traceId": job.trace_id,
                "name": "media-job",
                "model": job.task,
                "modelParameters": {"prompt": job.prompt},
                "usage": {"input": 0, "output": 0, "total": 0},
                "input": {
                    "task": job.task,
                    "input_files": [f.filename for f in job.input_files],
                    "options": job.options,
                },
                "output": {
                    "status": job.status,
                    "output_files": [f.filename for f in job.output_files],
                    "error": job.error,
                },
                "latency": job.duration_ms,
            }
        )


_client: LangfuseClient | None = None


def get_client(settings: Settings) -> LangfuseClient:
    global _client
    if _client is None:
        _client = LangfuseClient(settings)
    return _client
