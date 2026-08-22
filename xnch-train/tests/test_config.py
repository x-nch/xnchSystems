"""XtrainSettings loads from XTRAIN_-prefixed env vars with safe defaults."""
from pathlib import Path

from xnch_train.config import XtrainSettings


def test_defaults_are_safe(settings: XtrainSettings) -> None:
    s = XtrainSettings(dataset_dir=None, postgres_url=None)
    assert s.gate_epsilon == 0.02
    assert s.serving_regression_bound_pct == 10.0
    assert s.extract_page_size == 100


def test_env_override(settings: XtrainSettings) -> None:
    assert settings.dataset_dir == Path("/tmp/xtrain-test-datasets")
    assert settings.langfuse_host == "http://lf.test"
    assert settings.pseudonymize_secret == "unit-secret"
