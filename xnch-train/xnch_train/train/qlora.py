"""QLoRA SFT trainer for Ornith customization (Phase 1)."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_R = 16
_DEFAULT_EPOCHS = 1
_ATTN_MODULES = ["q_proj", "k_proj", "v_proj", "o_proj"]


@dataclass
class SftResult:
    adapter_dir: Path
    metrics: dict[str, float] = field(default_factory=dict)


def _validate_manifest(dataset_dir: Path) -> None:
    manifest = dataset_dir / "scrub_manifest.json"
    if not manifest.exists():
        raise ValueError(f"dataset {dataset_dir} has no scrub_manifest.json (refusing unscrubbed data)")


def _load_records(dataset_dir: Path) -> list[str]:
    _validate_manifest(dataset_dir)
    out: list[str] = []
    with (dataset_dir / "records.jsonl").open() as fh:
        for line in fh:
            if line.strip():
                out.append(line.strip())
    return out


def _fake_sft(base_model: str, dataset_dir: Path, out_dir: Path, r: int) -> SftResult:
    adapter = out_dir / "adapter"
    adapter.mkdir(parents=True, exist_ok=True)
    (adapter / "adapter_config.json").write_text(json.dumps({"r": r, "base": base_model}))
    (adapter / "adapter_model.safetensors").write_bytes(b"FAKE")
    return SftResult(adapter_dir=adapter, metrics={"train_loss": 0.5})


def run_sft(
    *,
    base_model: str,
    dataset_dir: Path,
    out_dir: Path,
    r: int = _DEFAULT_R,
    lora_modules: str = "attention",
    epochs: int = _DEFAULT_EPOCHS,
    fake: bool = False,
) -> SftResult:
    """Run QLoRA SFT. When fake=True, skip model load (unit-test path)."""
    records = _load_records(dataset_dir)
    logger.info("SFT on %d records, base=%s r=%d epochs=%d", len(records), base_model, r, epochs)
    if fake:
        return _fake_sft(base_model, dataset_dir, out_dir, r)
    # NOTE: real path imports torch/peft/trl lazily so unit tests never import them.
    from peft import LoraConfig  # type: ignore
    from transformers import (  # type: ignore
        AutoModelForCausalLM,
        AutoTokenizer,
        BitsAndBytesConfig,
        TrainingArguments,
    )
    from trl import SFTTrainer  # type: ignore

    quant_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
    )
    model = AutoModelForCausalLM.from_pretrained(
        base_model,
        quantization_config=quant_config,
        device_map="auto",
        trust_remote_code=True,
    )
    tokenizer = AutoTokenizer.from_pretrained(base_model, trust_remote_code=True)
    lora_config = LoraConfig(
        r=r,
        lora_alpha=r * 2,
        target_modules=_ATTN_MODULES if lora_modules == "attention" else None,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        args=TrainingArguments(
            output_dir=str(out_dir),
            num_train_epochs=epochs,
            per_device_train_batch_size=1,
            gradient_checkpointing=True,
            optim="paged_adamw_8bit",
            logging_steps=10,
        ),
        train_dataset=records,
        peft_config=lora_config,
        max_seq_length=2048,
        dataset_text_field="text",
    )
    result = trainer.train()
    final_loss = float(result.training_loss) if getattr(result, "training_loss", None) is not None else 0.0
    trainer.save_model(out_dir / "adapter")
    return SftResult(adapter_dir=out_dir / "adapter", metrics={"train_loss": final_loss})
