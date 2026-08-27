"""QLoRA SFT trainer: fake (unit-test) path, manifest guard, and lazy-import contract."""
import pytest

from xnch_train.train import SftResult, run_sft


def test_run_sft_writes_adapter_and_metrics(tmp_path: pytest.TempPathFactory) -> None:
    base = tmp_path / "base"  # tiny fake dir; fake=True avoids model load
    base.mkdir(parents=True, exist_ok=True)
    ds = tmp_path / "ds"
    ds.mkdir(parents=True, exist_ok=True)
    (ds / "records.jsonl").write_text('{"text":"hi"}\n')
    (ds / "scrub_manifest.json").write_text('{"version":"1"}')
    res = run_sft(base_model=str(base), dataset_dir=ds, out_dir=tmp_path / "out", fake=True)
    assert (tmp_path / "out" / "adapter").is_dir()
    assert "train_loss" in res.metrics
    assert isinstance(res, SftResult)


def test_run_sft_adapter_contains_config_and_weights(tmp_path: pytest.TempPathFactory) -> None:
    ds = tmp_path / "ds"
    ds.mkdir(parents=True, exist_ok=True)
    (ds / "records.jsonl").write_text('{"text":"hi"}\n')
    (ds / "scrub_manifest.json").write_text('{"version":"1"}')
    adapter = tmp_path / "out" / "adapter"
    run_sft(base_model="b", dataset_dir=ds, out_dir=tmp_path / "out", fake=True)
    assert (adapter / "adapter_config.json").is_file()
    assert (adapter / "adapter_model.safetensors").is_file()


def test_run_sft_refuses_dataset_without_manifest(tmp_path: pytest.TempPathFactory) -> None:
    ds = tmp_path / "ds"
    ds.mkdir(parents=True, exist_ok=True)
    (ds / "records.jsonl").write_text('{"text":"hi"}\n')
    with pytest.raises(ValueError, match="no scrub_manifest.json"):
        run_sft(base_model="b", dataset_dir=ds, out_dir=tmp_path / "out", fake=True)


def test_qlora_imports_without_torch() -> None:
    """Importing the trainer must not execute `import torch` at module scope."""
    import sys

    assert "torch" not in sys.modules
    import importlib

    import xnch_train.train.qlora as qlora  # noqa: F401
    importlib.reload(qlora)
    assert "torch" not in sys.modules, "torch was imported during trainer import"
