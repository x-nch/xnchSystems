"""Real executors for the media pipeline.

- QwenVlExecutor: `understand` -> LiteLLM proxy -> vLLM Qwen2.5-VL
  (image/video understanding -> job.result_text, traced to Langfuse).
- ComfyExecutor: generate/edit/upscale/i2v/t2v/v2v -> ComfyUI /prompt,
  substituting workflow placeholders, copying inputs into ComfyUI's input
  dir, polling /history, and collecting outputs into the outbox.

The queue holds the GPU slot (semaphore=1) for the whole executor call, so
concurrent jobs serialize against the single 3090.
"""
import asyncio
import base64
import json
import logging
import random
import shutil
import time
import uuid
from pathlib import Path
from typing import Any

import httpx

from .config import Settings
from .langfuse import LangfuseClient
from .models import FileKind, FileRecord, MediaJob
from .tasks import Engine, get_task_spec, stub_executor

logger = logging.getLogger(__name__)

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
_STRING_PLACEHOLDERS = {"<PROMPT>", "<INPUT_IMAGE>", "<INPUT_IMAGE2>", "<OUTPUT_PREFIX>"}
_INT_PLACEHOLDERS = {"<SEED>", "<VIDEO_LENGTH>", "<LAST_FRAME>"}

_EXT_CONTENT_TYPES: dict[str, str] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
}


class ComfyExecutor:
    """Dispatch a job to ComfyUI and collect output files into the outbox."""

    def __init__(
        self,
        settings: Settings,
        client: httpx.AsyncClient | None = None,
        timeout_s: int = 3600,
    ) -> None:
        self._settings = settings
        self._timeout_s = timeout_s
        self._client = client or httpx.AsyncClient(
            base_url=settings.comfy_url, timeout=httpx.Timeout(60.0)
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __call__(self, job: MediaJob) -> list[FileRecord]:
        spec = get_task_spec(job.task)
        if spec is None or not spec.comfy_workflow:
            raise ValueError(f"task '{job.task}' has no ComfyUI workflow")

        template = self._settings.workflows_dir / f"{spec.comfy_workflow}.json"
        workflow = json.loads(template.read_text())

        mapping = self._copy_inputs(job)
        self._substitute(workflow, job, mapping)
        logger.info("queueing comfy workflow %s for job %s", spec.comfy_workflow, job.job_id)

        prompt_id = await self._queue_prompt(workflow)
        history = await self._wait_history(prompt_id)
        return self._collect_outputs(history, job)

    def _copy_inputs(self, job: MediaJob) -> dict[str, str]:
        """Copy job inputs into ComfyUI's input dir (root — LoadImage/LoadVideo
        file pickers list from there).

        Returns a map of placeholder -> filename as seen by ComfyUI.
        """
        mapping: dict[str, str] = {}
        dest_dir = self._settings.comfy_input_dir
        dest_dir.mkdir(parents=True, exist_ok=True)
        for index, record in enumerate(job.input_files):
            src = Path(record.path)
            name = f"{job.job_id[:8]}_{record.filename}"
            shutil.copyfile(src, dest_dir / name)
            placeholder = "<INPUT_IMAGE>" if index == 0 else "<INPUT_IMAGE2>"
            mapping[placeholder] = name
            logger.info("copied %s -> %s/%s", src, dest_dir, name)
        return mapping

    def _substitute(
        self, workflow: dict[str, Any], job: MediaJob, mapping: dict[str, str]
    ) -> None:
        seed = int(job.options.get("seed", random.randrange(1 << 31)))
        length = int(job.options.get("length", 81))
        last_frame = int(job.options.get("last_frame", 80))
        values: dict[str, object] = {
            "<PROMPT>": job.prompt,
            "<INPUT_IMAGE>": mapping.get("<INPUT_IMAGE>", ""),
            "<INPUT_IMAGE2>": mapping.get("<INPUT_IMAGE2>", ""),
            "<OUTPUT_PREFIX>": f"mg_{job.job_id[:8]}",
            "<SEED>": seed,
            "<VIDEO_LENGTH>": length,
            "<LAST_FRAME>": last_frame,
        }
        for node in workflow.values():
            for key, value in node["inputs"].items():
                if isinstance(value, str) and value in values:
                    node["inputs"][key] = values[value]

    async def _queue_prompt(self, workflow: dict[str, Any]) -> str:
        payload = {"prompt": workflow, "client_id": "media-gateway"}
        resp = await self._client.post("/prompt", json=payload)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise RuntimeError(f"ComfyUI rejected prompt: {data['error']}")
        return data["prompt_id"]

    async def _wait_history(self, prompt_id: str) -> dict[str, Any]:
        deadline = time.time() + self._timeout_s
        while time.time() < deadline:
            resp = await self._client.get(f"/history/{prompt_id}")
            if resp.status_code == 404:
                await asyncio.sleep(2)
                continue
            resp.raise_for_status()
            history = resp.json()
            if prompt_id in history:
                return history[prompt_id]
            await asyncio.sleep(2)
        raise TimeoutError(f"ComfyUI job {prompt_id} did not finish in {self._timeout_s}s")

    def _collect_outputs(self, history: dict[str, Any], job: MediaJob) -> list[FileRecord]:
        status = history.get("status", {})
        status_str = status.get("status_str", "success")
        if status_str != "success":
            raise RuntimeError(self._describe_failure(status))

        records: list[FileRecord] = []
        self._settings.outbox_dir.mkdir(parents=True, exist_ok=True)
        for node_out in history.get("outputs", {}).values():
            for key in ("images", "gifs", "videos"):
                for item in node_out.get(key, []):
                    subfolder = item.get("subfolder", "")
                    filename = item.get("filename")
                    src = self._settings.comfy_output_dir / subfolder / filename
                    if not src.is_file():
                        logger.warning("ComfyUI output missing: %s", src)
                        continue
                    ext = src.suffix.lower()
                    content_type = _EXT_CONTENT_TYPES.get(
                        ext, "application/octet-stream"
                    )
                    file_id = uuid.uuid4().hex
                    dest = self._settings.outbox_dir / f"{file_id}{ext}"
                    shutil.copyfile(src, dest)
                    records.append(
                        FileRecord(
                            file_id=file_id,
                            filename=filename,
                            path=str(dest),
                            content_type=content_type,
                            size_bytes=src.stat().st_size,
                            kind=FileKind.OUTBOX,
                        )
                    )
                    logger.info(
                        "comfy output %s -> %s (%d bytes)", src, dest, src.stat().st_size
                    )
        return records

    @staticmethod
    def _describe_failure(status: dict[str, Any]) -> str:
        """Extract the real error from ComfyUI history status.messages.

        Messages are [event_type, data] pairs; execution_error carries the
        exception payload, execution_interrupted is self-explanatory.
        """
        for event, data in status.get("messages") or []:
            if event == "execution_error":
                exc_type = data.get("exception_type", "")
                exc_msg = data.get("exception_message", "")
                detail = f"{exc_type}: {exc_msg}" if exc_type else str(data)[:300]
                return f"ComfyUI execution error: {detail}"
            if event == "execution_interrupted":
                return f"ComfyUI execution interrupted: {data}"
        return f"ComfyUI job failed (status_str={status.get('status_str')})"


class QwenVlExecutor:
    """`understand` task -> LiteLLM proxy -> vLLM Qwen2.5-VL (multimodal)."""

    def __init__(
        self,
        settings: Settings,
        client: httpx.AsyncClient | None = None,
        langfuse: LangfuseClient | None = None,
    ) -> None:
        self._settings = settings
        self._langfuse = langfuse
        self._client = client or httpx.AsyncClient(
            base_url=settings.litellm_url, timeout=httpx.Timeout(120.0)
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __call__(self, job: MediaJob) -> list[FileRecord]:
        content: list[dict[str, Any]] = [
            {"type": "text", "text": job.prompt or "Describe this image."}
        ]
        for record in job.input_files:
            ext = Path(record.path).suffix.lower().lstrip(".")
            mime = record.content_type or _EXT_CONTENT_TYPES.get(
                f".{ext}", "application/octet-stream"
            )
            data = base64.b64encode(Path(record.path).read_bytes()).decode()
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{data}"},
                }
            )

        started = time.time()
        headers = {}
        if self._settings.litellm_key:
            headers["Authorization"] = f"Bearer {self._settings.litellm_key}"
        resp = await self._client.post(
            "/chat/completions",
            headers=headers,
            json={
                "model": self._settings.qwen_model,
                "messages": [{"role": "user", "content": content}],
                "max_tokens": self._settings.qwen_max_tokens,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        latency_ms = int((time.time() - started) * 1000)
        tokens = data.get("usage", {}).get("total_tokens", 0)

        job.result_text = text
        logger.info("qwen-vl job %s: %d tokens in %dms", job.job_id, tokens, latency_ms)
        if self._langfuse is not None:
            try:
                await self._langfuse.trace_llm_call(
                    prompt=job.prompt or "(image input)",
                    response=text,
                    model=self._settings.qwen_model,
                    latency_ms=latency_ms,
                    tokens_used=tokens,
                    trace_id=job.trace_id,
                )
            except Exception:
                logger.debug("langfuse llm trace failed", exc_info=True)
        return []


class Dispatcher:
    """Routes jobs to the right engine based on the task registry."""

    def __init__(
        self, settings: Settings, langfuse: LangfuseClient | None = None
    ) -> None:
        self._comfy = ComfyExecutor(settings)
        self._qwen = QwenVlExecutor(settings, langfuse=langfuse)

    async def aclose(self) -> None:
        await self._comfy.aclose()
        await self._qwen.aclose()

    async def __call__(self, job: MediaJob) -> list[FileRecord]:
        spec = get_task_spec(job.task)
        if spec is None:
            raise ValueError(f"unknown task '{job.task}'")
        if spec.engine == Engine.COMFY:
            return await self._comfy(job)
        if spec.engine == Engine.QWEN_VL:
            return await self._qwen(job)
        return await stub_executor(job)
