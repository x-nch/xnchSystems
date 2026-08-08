"""Load MCP bridge server definitions from YAML."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from xnch_mcp.tiers import ToolTier

_TIER_MAP = {
    "T0_READ": ToolTier.T0_READ,
    "T0": ToolTier.T0_READ,
    "T1_WRITE": ToolTier.T1_WRITE,
    "T1": ToolTier.T1_WRITE,
    "T2_EXEC": ToolTier.T2_EXEC,
    "T2": ToolTier.T2_EXEC,
}


@dataclass(frozen=True)
class ServerConfig:
    server_id: str
    enabled: bool
    actors: frozenset[str]
    tier: ToolTier
    tool_prefix: str
    command: str
    args: list[str]
    env: dict[str, str]
    allow_tools: frozenset[str] | None
    deny_tools: frozenset[str]


@dataclass
class BridgeConfig:
    servers: dict[str, ServerConfig] = field(default_factory=dict)

    @property
    def has_enabled_servers(self) -> bool:
        return any(s.enabled for s in self.servers.values())


def _parse_tier(raw: str) -> ToolTier:
    key = raw.strip().upper()
    if key not in _TIER_MAP:
        raise ValueError(f"Unknown tier: {raw!r}")
    return _TIER_MAP[key]


def _parse_server(server_id: str, raw: dict[str, Any]) -> ServerConfig:
    command = raw.get("command")
    if not command:
        raise ValueError(f"server {server_id!r}: command is required")

    args = raw.get("args") or []
    if isinstance(args, str):
        args = [args]

    allow = raw.get("allow_tools")
    allow_tools = frozenset(allow) if allow else None
    deny = raw.get("deny_tools") or []
    prefix = str(raw.get("tool_prefix", f"{server_id}_"))

    return ServerConfig(
        server_id=server_id,
        enabled=bool(raw.get("enabled", True)),
        actors=frozenset(raw.get("actors") or ["nexi", "operator"]),
        tier=_parse_tier(str(raw.get("tier", "T0_READ"))),
        tool_prefix=prefix,
        command=str(command),
        args=[str(a) for a in args],
        env={str(k): str(v) for k, v in (raw.get("env") or {}).items()},
        allow_tools=allow_tools,
        deny_tools=frozenset(str(t) for t in deny),
    )


def load_bridge_config(path: Path) -> BridgeConfig:
    if not path.is_file():
        return BridgeConfig()

    data = yaml.safe_load(path.read_text()) or {}
    servers_raw = data.get("servers") or {}
    servers: dict[str, ServerConfig] = {}
    for server_id, raw in servers_raw.items():
        if not isinstance(raw, dict):
            raise ValueError(f"server {server_id!r}: expected mapping")
        servers[server_id] = _parse_server(server_id, raw)
    return BridgeConfig(servers=servers)
