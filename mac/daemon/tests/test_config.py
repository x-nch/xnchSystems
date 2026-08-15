from daemon.config import DaemonConfig


def test_defaults(monkeypatch):
    for var in ("XNCH_BASE_URL", "XNCH_AUTH_SECRET", "XNCH_AUTH_TOKEN",
                "XNCH_ACTOR", "NEXI_BASE_URL", "MEDIA_GATEWAY_URL",
                "XNCH_VOICE_SAMPLE_RATE", "XNCH_VOICE_INPUT_DEVICE",
                "XNCH_VOICE_OUTPUT_DEVICE"):
        monkeypatch.delenv(var, raising=False)
    cfg = DaemonConfig.from_env()
    assert cfg.base_url == "http://192.168.1.10:8001"
    assert cfg.actor == "operator"
    assert cfg.nexi_url == "http://192.168.1.9:8001"
    assert cfg.media_url == "http://192.168.1.9:8090"
    assert cfg.sample_rate == 16000
    assert cfg.input_device is None
    assert cfg.output_device is None


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("XNCH_BASE_URL", "http://10.0.0.5:8001/")
    monkeypatch.setenv("XNCH_VOICE_INPUT_DEVICE", "2")
    monkeypatch.setenv("XNCH_VOICE_OUTPUT_DEVICE", "AirPods")
    cfg = DaemonConfig.from_env()
    assert cfg.base_url == "http://10.0.0.5:8001"
    assert cfg.input_device == 2
    assert cfg.output_device == "AirPods"


def test_auth_header_priority(monkeypatch):
    monkeypatch.setenv("XNCH_AUTH_TOKEN", "tok")
    monkeypatch.setenv("XNCH_AUTH_SECRET", "secret")
    assert DaemonConfig.from_env().auth_header() == "Bearer tok"
    monkeypatch.delenv("XNCH_AUTH_TOKEN", raising=False)
    header = DaemonConfig.from_env().auth_header()
    assert header.startswith("Bearer ")
    monkeypatch.delenv("XNCH_AUTH_SECRET", raising=False)
    assert DaemonConfig.from_env().auth_header() == "actor:operator"
