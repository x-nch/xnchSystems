"""Task registry + executors for the media pipeline.

Task -> engine mapping:
  understand        -> qwen-vl   (vLLM :8083, via LiteLLM on Node A)
  generate_image    -> comfy     (flux_t2i workflow, step 3)
  edit_image        -> comfy     (flux_img2img / flux_inpaint, step 3)
  upscale_image     -> comfy     (flux_upscale, step 3)
  image_to_video    -> comfy     (wan_i2v, step 3)
  text_to_video     -> comfy     (wan_t2v, step 3)
  video_to_video    -> comfy     (wan_v2v, step 3)

Step 2 has no ComfyUI wiring yet: the executor is a stub that simulates the
run so the queue/GPU-slot/status lifecycle can be exercised end-to-end.
"""
import asyncio
import logging
from enum import StrEnum

from pydantic import BaseModel, Field

from .models import MediaJob, FileRecord

logger = logging.getLogger(__name__)


class Engine(StrEnum):
    QWEN_VL = "qwen-vl"
    COMFY = "comfy"


class OutputKind(StrEnum):
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"


class TaskSpec(BaseModel):
    name: str
    engine: Engine
    output_kind: OutputKind
    min_inputs: int = 0
    max_inputs: int = 1
    comfy_workflow: str | None = Field(default=None)
    description: str = ""


_TASKS: dict[str, TaskSpec] = {
    "understand": TaskSpec(
        name="understand",
        engine=Engine.QWEN_VL,
        output_kind=OutputKind.TEXT,
        min_inputs=1,
        max_inputs=4,
        description="Caption / summarize / answer questions about image or video",
    ),
    "generate_image": TaskSpec(
        name="generate_image",
        engine=Engine.COMFY,
        output_kind=OutputKind.IMAGE,
        min_inputs=0,
        max_inputs=0,
        comfy_workflow="flux_t2i",
        description="Text-to-image with Flux",
    ),
    "edit_image": TaskSpec(
        name="edit_image",
        engine=Engine.COMFY,
        output_kind=OutputKind.IMAGE,
        min_inputs=1,
        max_inputs=2,
        comfy_workflow="flux_img2img",
        description="Transform/restyle an image (img2img or inpainting)",
    ),
    "upscale_image": TaskSpec(
        name="upscale_image",
        engine=Engine.COMFY,
        output_kind=OutputKind.IMAGE,
        min_inputs=1,
        max_inputs=1,
        comfy_workflow="flux_upscale",
        description="Upscale an image",
    ),
    "image_to_video": TaskSpec(
        name="image_to_video",
        engine=Engine.COMFY,
        output_kind=OutputKind.VIDEO,
        min_inputs=1,
        max_inputs=1,
        comfy_workflow="wan_i2v",
        description="Animate a still image with Wan 2.2",
    ),
    "text_to_video": TaskSpec(
        name="text_to_video",
        engine=Engine.COMFY,
        output_kind=OutputKind.VIDEO,
        min_inputs=0,
        max_inputs=0,
        comfy_workflow="wan_t2v",
        description="Text-to-video with Wan 2.2",
    ),
    "video_to_video": TaskSpec(
        name="video_to_video",
        engine=Engine.COMFY,
        output_kind=OutputKind.VIDEO,
        min_inputs=1,
        max_inputs=1,
        comfy_workflow="wan_v2v",
        description="Edit/restyle an existing video with Wan 2.2",
    ),
}


def get_task_spec(task: str) -> TaskSpec | None:
    return _TASKS.get(task)


def list_tasks() -> list[TaskSpec]:
    return list(_TASKS.values())


async def stub_executor(job: MediaJob) -> list[FileRecord]:
    """Placeholder — real dispatch (ComfyUI / qwen-vl) lands in step 3+."""
    logger.warning(
        "executor not wired yet for task=%s job=%s (ComfyUI dispatch in step 3); simulating run",
        job.task,
        job.job_id,
    )
    await asyncio.sleep(0.5)
    job.result_text = f"[stub] {job.task} simulated — ComfyUI/Qwen-VL wiring lands in step 6"
    return []
