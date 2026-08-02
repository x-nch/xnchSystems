from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from xnch.security.trust_model import (
    TrustLevel,
    get_trust_level,
    requires_trust,
    ACTOR_TRUST_MAP,
)


def test_trust_level_values():
    assert TrustLevel.UNTRUSTED.value == 1
    assert TrustLevel.EXTERNAL_AGENT.value == 2
    assert TrustLevel.TRUSTED_AGENT.value == 3
    assert TrustLevel.OWNER.value == 4
    assert TrustLevel.SYSTEM.value == 5


def test_get_trust_level_known():
    assert get_trust_level("nexi") == TrustLevel.SYSTEM
    assert get_trust_level("admin") == TrustLevel.OWNER
    assert get_trust_level("operator") == TrustLevel.OWNER
    assert get_trust_level("opencode") == TrustLevel.TRUSTED_AGENT
    assert get_trust_level("agent") == TrustLevel.TRUSTED_AGENT
    assert get_trust_level("perception_daemon") == TrustLevel.TRUSTED_AGENT
    assert get_trust_level("consolidation_job") == TrustLevel.TRUSTED_AGENT
    assert get_trust_level("viewer") == TrustLevel.EXTERNAL_AGENT


def test_get_trust_level_unknown():
    assert get_trust_level("unknown_actor") == TrustLevel.UNTRUSTED
    assert get_trust_level("openclaw") == TrustLevel.UNTRUSTED
    assert get_trust_level("claude_code") == TrustLevel.UNTRUSTED


def test_get_trust_level_external():
    assert get_trust_level("external") == TrustLevel.UNTRUSTED


def test_actor_trust_map_completeness():
    expected = {"nexi", "admin", "operator", "agent", "viewer",
                "opencode", "perception_daemon", "consolidation_job", "external"}
    assert set(ACTOR_TRUST_MAP.keys()) == expected


@pytest.mark.asyncio
async def test_requires_trust_passes():
    mock_request = MagicMock(spec=Request)
    mock_request.headers = {"X-Actor-Role": "nexi"}

    @requires_trust(TrustLevel.TRUSTED_AGENT)
    async def my_handler(req):
        return "ok"

    result = await my_handler(mock_request)
    assert result == "ok"


@pytest.mark.asyncio
async def test_requires_trust_fails():
    mock_request = MagicMock(spec=Request)
    mock_request.headers = {"X-Actor-Role": "external"}

    @requires_trust(TrustLevel.OWNER)
    async def my_handler(req):
        return "ok"

    with pytest.raises(HTTPException) as exc:
        await my_handler(mock_request)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_requires_trust_no_request():
    @requires_trust(TrustLevel.OWNER)
    async def my_handler():
        return "ok"

    with pytest.raises(HTTPException) as exc:
        await my_handler()
    assert exc.value.status_code == 500


@pytest.mark.asyncio
async def test_requires_trust_kwargs():
    mock_request = MagicMock(spec=Request)
    mock_request.headers = {"X-Actor-Role": "admin"}

    @requires_trust(TrustLevel.OWNER)
    async def my_handler(request):
        return "ok"

    result = await my_handler(request=mock_request)
    assert result == "ok"
