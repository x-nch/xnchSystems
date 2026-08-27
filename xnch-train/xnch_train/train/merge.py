"""Adapter merge + GPTQ requant for Ornith customization (Phase 1).

Gate G2 (checkpoint promotion): the eval-harness promotion gate emits a
`checkpoint.promotion` proposal keyed by `checkpoint_id`; that id is the
immutable primary key of the checkpoint registry (see `registry.py`).

The real (production) merge path requires a GPU and the `torch`/`peft`/
`auto-gptq` (or `optimum`) stack, so those imports are LAZY — performed only
inside the real branch of `merge_and_requant`. Importing this module (or
`xnch_train.train`) must NOT pull in `torch`, so it stays unit-testable in a
repo venv without torch installed.

Requantization target: `--quantization gptq_marlin` to match
`vllm-ornith.service`'s `quantization gptq_marlin`. If the original Ornith
GPTQ recipe is unrecoverable, the documented default recipe below (gptq_marlin)
is the fallback; any deviation MUST be recorded in the eval report (Task 6).
"""
from __future__ import annotations

from pathlib import Path


def _requant_gptq_marlin(out_dir: Path) -> None:
    """Requantize the merged fp16 model in `out_dir` to GPTQ (gptq_marlin).

    Documented default recipe (Gate G2 fallback). The merged fp16 safetensors
    produced by `merge_and_unload()`/`save_pretrained` are consumed by the
    auto-gptq / optimum GPTQ calibration pass targeting `--quantization
    gptq_marlin` so the artifact is directly loadable by vllm-ornith.service.

    The heavy imports (`auto_gptq` / `optimum` / `torch`) are intentionally
    deferred here so this module never imports torch at import time.
    """
    from auto_gptq import AutoGPTQForCausalLM  # type: ignore
    from auto_gptq.quantization import BaseQuantizeConfig  # type: ignore

    quantize_config = BaseQuantizeConfig(
        bits=4,
        group_size=128,
        desc_act=False,
        damp_percent=0.01,
    )
    model = AutoGPTQForCausalLM.from_pretrained(
        str(out_dir),
        quantize_config=quantize_config,
        torch_dtype="auto",
    )
    # In production this is fed the calibration dataset from the scrubbed
    # SFT corpus; the calibration set is wired in Step 5 (3090 window).
    model.quantize(calibration_dataset=None)  # type: ignore[arg-type]
    model.save_quantized(str(out_dir), use_safetensors=True)


def merge_and_requant(
    *,
    adapter_dir: Path,
    base_model: str,
    out_dir: Path,
    fake: bool = False,
) -> Path:
    """Merge a LoRA adapter into the fp16 base and requantize to GPTQ.

    Returns the output model directory. With ``fake=True`` no model is loaded:
    the merged dir is created and a ``requant.done`` marker is written so the
    unit-test path stays hardware-free. The real path is GPU/HW-gated and runs
    only in the Step 5 (3090) verification window.
    """
    if fake:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "requant.done").write_text(
            "fake merge+requant marker; real path is GPU-gated (Step 5)"
        )
        return out_dir

    # --- Real path (lazy heavy imports: never at module scope) ---
    import torch  # type: ignore
    from peft import PeftModel  # type: ignore
    from transformers import AutoModelForCausalLM  # type: ignore

    model = AutoModelForCausalLM.from_pretrained(
        base_model, torch_dtype=torch.float16
    )
    model = PeftModel.from_pretrained(model, adapter_dir)
    merged = model.merge_and_unload()
    merged.save_pretrained(out_dir)

    # GPTQ requant (gptq_marlin) — Gate G2 default recipe.
    _requant_gptq_marlin(out_dir)
    return out_dir
