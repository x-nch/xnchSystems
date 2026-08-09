"""Router tests."""

import pytest

from agent_gateway.router import get_adapter, route_model


def test_route_backend_model_pair() -> None:
    routed = route_model("cursor-agent/auto")
    assert routed.backend == "cursor-agent"
    assert routed.model == "auto"
    assert routed.model_id == "cursor-agent/auto"


def test_route_backend_only() -> None:
    routed = route_model("opencode")
    assert routed.backend == "opencode"
    assert routed.model is None


def test_route_unknown_model_uses_default_backend() -> None:
    routed = route_model("sonnet")
    assert routed.backend == "claude-code"
    assert routed.model == "sonnet"
    assert routed.model_id == "claude-code/sonnet"


def test_get_adapter_unknown_backend() -> None:
    with pytest.raises(ValueError, match="Unknown backend"):
        get_adapter("unknown")
