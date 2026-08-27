"""xtrain cycle observability + GPU-contention emission (Task 7).

Two fire-and-forget emitters that POST events to Langfuse's public trace API:

* ``CycleTracer`` — emits one ``/api/public/trace`` POST per cycle event
  (``cycle.begin`` / ``cycle.step`` / ``cycle.result``). It is intentionally
  SYNCHRONOUS and wrapped in try/except so a tracing failure can never raise
  into the training cycle. The cycle must keep running even when Langfuse is
  down (see ADR §5: job lifecycle + eval series + promotion/rollback events).
* ``GpuPoller`` — emits ``gpu.contention`` events (unit holding the GPU, OOM,
  vLLM restart). The polling loop itself lives in the shell script
  ``scripts/xtrain-gpu-poller.sh``; this class is the emitter it calls.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_LANGFUSE_TRACE_PATH = "/api/public/trace"


class CycleTracer:
    """Emit one Langfuse trace POST per cycle event, fire-and-forget.

    Each call is best-effort: any transport/auth/serialization error is logged
    as a warning and swallowed so the training cycle is never interrupted by a
    tracing failure.
    """

    def __init__(
        self,
        langfuse_host: str,
        public_key: str = "",
        secret_key: str = "",
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._public_key = public_key
        self._secret_key = secret_key
        self._c = httpx.Client(
            base_url=langfuse_host,
            auth=(public_key, secret_key) if (public_key or secret_key) else None,
            transport=transport or httpx.HTTPTransport(),
        )

    def begin(self, run_id: str) -> None:
        """Emit ``cycle.begin`` — marks the start of a training cycle."""
        self._post(
            run_id,
            "cycle.begin",
            {"run_id": run_id},
        )

    def step(self, name: str, metrics: dict[str, float]) -> None:
        """Emit ``cycle.step`` — one span per named step (e.g. ``train``)."""
        self._post(
            name,
            "cycle.step",
            {"step": name, "metrics": metrics},
        )

    def result(self, *, eligible: bool, report_id: str) -> None:
        """Emit ``cycle.result`` — the promotion eligibility verdict."""
        self._post(
            report_id,
            "cycle.result",
            {"report_id": report_id, "eligible": eligible},
        )

    def _post(self, trace_id: str, event_type: str, payload: dict[str, Any]) -> None:
        body: dict[str, Any] = {
            "id": trace_id,
            "name": event_type,
            "metadata": payload,
        }
        try:
            self._c.post(_LANGFUSE_TRACE_PATH, json=body)
        except Exception as exc:  # pragma: no cover - defensive, never breaks cycle
            logger.warning("CycleTracer %s emit failed: %s", event_type, exc)


class GpuPoller:
    """Emit ``gpu.contention`` events to Langfuse, fire-and-forget.

    The actual ``nvidia-smi`` polling loop lives in
    ``scripts/xtrain-gpu-poller.sh``; this class is the emitter that loop calls
    to record contention (unit holding the GPU, OOM, vLLM restart).
    """

    def __init__(
        self,
        langfuse_host: str,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._c = httpx.Client(
            base_url=langfuse_host,
            transport=transport or httpx.HTTPTransport(),
        )

    def emit(self, event: dict[str, Any]) -> None:
        """POST a ``gpu.contention`` event to Langfuse."""
        body: dict[str, Any] = {
            "id": event.get("id", "gpu-contention"),
            "name": "gpu.contention",
            "metadata": event,
        }
        try:
            self._c.post(_LANGFUSE_TRACE_PATH, json=body)
        except Exception as exc:  # pragma: no cover - defensive, never breaks loop
            logger.warning("GpuPoller emit failed: %s", exc)
