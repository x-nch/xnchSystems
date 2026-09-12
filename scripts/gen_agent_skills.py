"""Generate agentskills.io-format SKILL.md docs for xnch MCP tools.

Usage: python scripts/gen_agent_skills.py --out <dir>
"""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from xnch_mcp.registry import get_registry


def _skill_md(tool) -> str:
    front = {
        "name": tool.name,
        "description": tool.description,
        "tier": tool.tier.name,
    }
    body = [
        "---",
        yaml.safe_dump(front, sort_keys=False).strip(),
        "---",
        "",
        f"# {tool.name}",
        "",
        f"{tool.description}",
        "",
        "## Input schema",
        "",
        "```yaml",
        yaml.safe_dump(tool.input_schema, sort_keys=False).strip(),
        "```",
        "",
    ]
    return "\n".join(body)


def generate_skills(registry: list, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for tool in registry:
        path = out_dir / f"{tool.name}.skill.md"
        path.write_text(_skill_md(tool))
        written.append(path)
    return written


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    paths = generate_skills(get_registry(), args.out)
    print(f"wrote {len(paths)} skills to {args.out}")


if __name__ == "__main__":
    main()