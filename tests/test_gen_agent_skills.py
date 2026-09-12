"""gen_agent_skills: SKILL.md generation from tool defs."""

from __future__ import annotations

from pathlib import Path

from xnch_mcp.tool_def import ToolDef
from xnch_mcp.tiers import ToolTier

from scripts.gen_agent_skills import generate_skills


def _tool(name: str = "xnch_memory_recall") -> ToolDef:
    async def handler(app, actor, args):  # pragma: no cover
        return {}

    return ToolDef(
        name=name,
        description="Recall episodes.",
        tier=ToolTier.T0_READ,
        input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
        handler=handler,
    )


def test_generates_skill_md(tmp_path: Path) -> None:
    paths = generate_skills([_tool()], tmp_path)
    assert len(paths) == 1
    content = paths[0].read_text()
    assert "xnch_memory_recall" in content
    assert "description" in content
    assert "T0_READ" in content


def test_no_tools_no_files(tmp_path: Path) -> None:
    assert generate_skills([], tmp_path) == []