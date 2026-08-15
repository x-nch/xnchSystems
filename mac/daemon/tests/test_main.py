from daemon.config import DaemonConfig
from daemon.main import Daemon


def _cfg() -> DaemonConfig:
    return DaemonConfig(
        base_url="http://xnch:8001",
        auth_secret="",
        auth_token="",
        actor="operator",
        nexi_url="http://nexi:8001",
        media_url="http://media:8090",
        sample_rate=16000,
        input_device=None,
        output_device=None,
        ws_host="127.0.0.1",
        ws_port=9001,
        http_port=9002,
    )


def test_arm_disarm_roundtrip():
    d = Daemon(_cfg())
    d.handle_command({"type": "arm"})
    assert d._armed is True
    d.handle_command({"type": "disarm"})
    assert d._armed is False


def test_handle_segment_garbage_is_skipped(monkeypatch):
    d = Daemon(_cfg())
    broadcasted = []

    class _FakeGateway:
        def voice_chat(self, *args, **kwargs):
            return {"transcript": "aa aaa aaa"}  # garbage → must not surface

    monkeypatch.setattr("daemon.main.broadcast", lambda p: broadcasted.append(p))
    d.gateway = _FakeGateway()
    d._handle_segment(b"\x00\x00" * 4800)
    assert all(p.get("type") != "voice_result" for p in broadcasted)


def test_probe_health_all_down(monkeypatch):
    d = Daemon(_cfg())

    class _DownGateway:
        def health(self):
            raise RuntimeError("down")

        def nexi_health(self):
            raise RuntimeError("down")

        def media_health(self):
            raise RuntimeError("down")

    d.gateway = _DownGateway()
    assert d._probe_health() == {"xnch": "down", "nexi": "down", "media": "down"}
