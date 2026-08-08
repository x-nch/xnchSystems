"""Command execution policy — allowlist prefixes and deny patterns."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class ExecDenied(PermissionError):
    """Raised when a command is not permitted."""


@dataclass
class HostExecPolicy:
    allowed_prefixes: tuple[str, ...]


@dataclass
class ExecPolicy:
    hosts: dict[str, HostExecPolicy]
    denied_substrings: tuple[str, ...]
    timeout_seconds: int
    max_output_bytes: int
    working_dir: Path

    def validate(self, host: str, command: str, cwd: str | None = None) -> tuple[list[str], Path]:
        if host not in self.hosts:
            raise ExecDenied(f"unknown host: {host}")

        cmd = command.strip()
        if not cmd:
            raise ValueError("command is required")

        lowered = cmd.lower()
        for bad in self.denied_substrings:
            if bad in lowered:
                raise ExecDenied(f"command contains denied pattern: {bad!r}")

        host_policy = self.hosts[host]
        if not any(lowered.startswith(p.lower()) for p in host_policy.allowed_prefixes):
            raise ExecDenied("command not in allowlist for this host")

        import shlex

        try:
            argv = shlex.split(cmd)
        except ValueError as exc:
            raise ExecDenied(f"invalid command syntax: {exc}") from exc

        if not argv:
            raise ExecDenied("empty command after parse")

        work = Path(cwd).expanduser().resolve() if cwd else self.working_dir.resolve()
        home = Path("/home/x-nch").resolve()
        try:
            work.relative_to(home)
        except ValueError as exc:
            raise ExecDenied("working directory must be under /home/x-nch") from exc

        return argv, work


def load_exec_policy(path: Path) -> ExecPolicy:
    with open(path) as f:
        data: dict[str, Any] = yaml.safe_load(f) or {}

    defaults = data.get("defaults") or {}
    hosts: dict[str, HostExecPolicy] = {}
    for name, cfg in (data.get("hosts") or {}).items():
        prefixes = tuple(cfg.get("allowed_prefixes") or [])
        if not prefixes:
            raise ValueError(f"host {name} has no allowed_prefixes")
        hosts[name] = HostExecPolicy(allowed_prefixes=prefixes)

    return ExecPolicy(
        hosts=hosts,
        denied_substrings=tuple(data.get("denied_substrings") or []),
        timeout_seconds=int(defaults.get("timeout_seconds", 45)),
        max_output_bytes=int(defaults.get("max_output_bytes", 65536)),
        working_dir=Path(defaults.get("working_dir", "/home/x-nch/xnchSystems")),
    )
