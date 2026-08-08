"""Tests for web search policy loading."""

from pathlib import Path

import pytest

from xnch_mcp.web.policy import load_web_search_policy


def test_load_web_search_policy(tmp_path: Path):
    path = tmp_path / "web-search.yaml"
    path.write_text(
        """
enabled: true
backend: searxng
searxng_url: http://127.0.0.1:8888
max_results: 5
engines: [duckduckgo, brave]
allowed_actors: [nexi]
"""
    )
    policy = load_web_search_policy(path)
    assert policy.enabled is True
    assert policy.searxng_url == "http://127.0.0.1:8888"
    assert policy.engines == ("duckduckgo", "brave")
    assert policy.allowed_actors == frozenset({"nexi"})


def test_load_web_search_policy_missing_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load_web_search_policy(tmp_path / "missing.yaml")
