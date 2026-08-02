from __future__ import annotations

from xnch.security.actor_sandbox import get_capabilities, CAPABILITY_MAP
from xnch.security.trust_model import TrustLevel


def test_system_capabilities():
    caps = get_capabilities("nexi")
    assert caps.can_write_memory is True
    assert caps.can_read_all_memory is True
    assert caps.can_trigger_jobs is True
    assert caps.can_modify_policies is True
    assert caps.can_access_perception is True


def test_owner_capabilities():
    caps = get_capabilities("operator")
    assert caps.can_write_memory is True
    assert caps.can_read_all_memory is True
    assert caps.can_trigger_jobs is True
    assert caps.can_modify_policies is False
    assert caps.can_access_perception is True


def test_removed_actor_is_untrusted():
    caps = get_capabilities("openclaw")
    assert caps.can_write_memory is False
    assert caps.can_read_all_memory is False


def test_trusted_agent_capabilities():
    caps = get_capabilities("opencode")
    assert caps.can_write_memory is True
    assert caps.can_read_all_memory is False
    assert caps.can_trigger_jobs is True
    assert caps.can_modify_policies is False
    assert caps.can_access_perception is False


def test_external_agent_capabilities():
    caps = get_capabilities("external")
    assert caps.can_write_memory is False
    assert caps.can_read_all_memory is False
    assert caps.can_trigger_jobs is False
    assert caps.can_modify_policies is False
    assert caps.can_access_perception is False


def test_untrusted_capabilities():
    caps = get_capabilities("unknown_actor")
    assert caps.can_write_memory is False
    assert caps.can_read_all_memory is False
    assert caps.can_trigger_jobs is False
    assert caps.can_modify_policies is False
    assert caps.can_access_perception is False


def test_capability_map_has_all_levels():
    for level in TrustLevel:
        assert level in CAPABILITY_MAP


def test_capability_map_untrusted_defaults():
    caps = CAPABILITY_MAP[TrustLevel.UNTRUSTED]
    assert all([
        not caps.can_write_memory,
        not caps.can_read_all_memory,
        not caps.can_trigger_jobs,
        not caps.can_modify_policies,
        not caps.can_access_perception,
    ])
