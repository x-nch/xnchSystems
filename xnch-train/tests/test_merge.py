"""Adapter merge + GPTQ requant: fake path and lazy-import contract."""
import sys

import pytest

from xnch_train.train.merge import merge_and_requant


def test_merge_fake_returns_dir_with_marker(tmp_path: pytest.TempPathFactory) -> None:
    out = merge_and_requant(
        adapter_dir=tmp_path / "adapter",
        base_model="b",
        out_dir=tmp_path / "o",
        fake=True,
    )
    assert isinstance(out, __import__("pathlib").Path)
    assert (out / "requant.done").is_file()


def test_merge_imports_without_torch() -> None:
    """Importing merge must not execute `import torch` at module scope."""
    import importlib

    assert "torch" not in sys.modules
    import xnch_train.train.merge as merge  # noqa: F401

    importlib.reload(merge)
    assert "torch" not in sys.modules, "torch was imported during merge import"
