"""Shared fixtures for xnch-train tests."""
import pytest

from xnch_train.config import XtrainSettings


@pytest.fixture(autouse=True)
def _xtrain_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate every test from the operator's real environment."""
    monkeypatch.setenv("XTRAIN_DATASET_DIR", "/tmp/xtrain-test-datasets")
    monkeypatch.setenv("XTRAIN_POSTGRES_URL", "postgresql://test:test@localhost:5432/test")
    monkeypatch.setenv("XTRAIN_LANGFUSE_HOST", "http://lf.test")
    monkeypatch.setenv("XTRAIN_LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("XTRAIN_LANGFUSE_SECRET_KEY", "sk-test")
    monkeypatch.setenv("XTRAIN_PSEUDONYMIZE_SECRET", "unit-secret")


@pytest.fixture()
def settings() -> XtrainSettings:
    return XtrainSettings()
