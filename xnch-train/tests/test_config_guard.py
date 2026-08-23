"""Empty pseudonymize secret must fail fast, not silently weaken scrubbing."""
import pytest
from pydantic import ValidationError

from xnch_train.config import XtrainSettings


def test_empty_pseudonymize_secret_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("XTRAIN_PSEUDONYMIZE_SECRET", raising=False)
    monkeypatch.setattr("xnch_train.config.XtrainSettings.model_config",
                        {**XtrainSettings.model_config, "env_file": None})
    with pytest.raises(ValidationError, match="XTRAIN_PSEUDONYMIZE_SECRET"):
        XtrainSettings(pseudonymize_secret="")


def test_nonempty_pseudonymize_secret_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("XTRAIN_PSEUDONYMIZE_SECRET", raising=False)
    s = XtrainSettings(pseudonymize_secret="strong-secret")
    assert s.pseudonymize_key() == b"strong-secret"
