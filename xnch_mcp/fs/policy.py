"""Filesystem path policy — allowlist roots and deny globs."""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class FsAccessDenied(PermissionError):
    """Raised when a path is outside policy or on the deny list."""


@dataclass(frozen=True)
class HostPolicy:
    roots: tuple[Path, ...]


@dataclass
class FsPolicy:
    hosts: dict[str, HostPolicy]
    deny_globs: tuple[str, ...]

    def resolve(self, host: str, path: str) -> Path:
        if host not in self.hosts:
            raise FsAccessDenied(f"unknown host: {host}")

        raw = path.strip()
        if not raw or "\0" in raw:
            raise ValueError("path is required")

        parts = Path(raw).parts
        if ".." in parts:
            raise FsAccessDenied("path traversal not allowed")

        host_policy = self.hosts[host]
        resolved_roots = [r.expanduser().resolve() for r in host_policy.roots]

        candidate = Path(raw)
        if candidate.is_absolute():
            resolved = candidate.expanduser().resolve()
        else:
            resolved = None
            for root in resolved_roots:
                trial = (root / raw).resolve()
                if _under_root(trial, root):
                    resolved = trial
                    break
            if resolved is None:
                resolved = (resolved_roots[0] / raw).resolve()

        if not any(_under_root(resolved, root) for root in resolved_roots):
            raise FsAccessDenied("path outside allowed roots")

        if resolved.is_symlink():
            target = resolved.resolve()
            if not any(_under_root(target, root) for root in resolved_roots):
                raise FsAccessDenied("symlink escapes allowed roots")
            resolved = target

        rel_for_deny = _relative_for_deny(resolved, resolved_roots)
        for pattern in self.deny_globs:
            if fnmatch.fnmatch(str(resolved), pattern) or fnmatch.fnmatch(rel_for_deny, pattern):
                raise FsAccessDenied("path denied by policy")

        return resolved


def _under_root(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _relative_for_deny(path: Path, roots: list[Path]) -> str:
    for root in roots:
        if _under_root(path, root):
            return str(path.relative_to(root)).replace("\\", "/")
    return str(path)


def load_fs_policy(path: Path) -> FsPolicy:
    with open(path) as f:
        data: dict[str, Any] = yaml.safe_load(f) or {}

    hosts: dict[str, HostPolicy] = {}
    for name, cfg in (data.get("hosts") or {}).items():
        roots = tuple(Path(r) for r in (cfg.get("roots") or []))
        if not roots:
            raise ValueError(f"host {name} has no roots")
        hosts[name] = HostPolicy(roots=roots)

    deny = tuple(data.get("deny_globs") or [])
    return FsPolicy(hosts=hosts, deny_globs=deny)
