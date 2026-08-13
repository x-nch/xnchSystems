#!/usr/bin/env python3
"""Validate ComfyUI workflow JSONs in this directory.

Checks: valid JSON, API-format structure (str-node-id -> {class_type, inputs}),
placeholders within the allowed contract, and every referenced node exists.
Exit code 0 on success. Stdlib only.

Usage:
    python workflows/validate.py
"""
import json
import re
import sys
from pathlib import Path

WORKFLOWS_DIR = Path(__file__).resolve().parent
PLACEHOLDER_RE = re.compile(r"<[A-Z_]+>")
ALLOWED_PLACEHOLDERS = {
    "<PROMPT>",
    "<INPUT_IMAGE>",
    "<INPUT_IMAGE2>",
    "<OUTPUT_PREFIX>",
    "<SEED>",
    "<VIDEO_LENGTH>",
    "<LAST_FRAME>",
}
EXPECTED_WORKFLOWS = {
    "flux_t2i",
    "flux_img2img",
    "flux_inpaint",
    "flux_upscale",
    "wan_i2v",
    "wan_t2v",
    "wan_v2v",
}


def validate_file(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        return [f"  {path.name}: invalid JSON: {exc}"]

    if not isinstance(data, dict):
        return [f"  {path.name}: top-level must be a dict"]

    node_ids: set[str] = set()
    placeholders: set[str] = set()

    for raw_id, node in data.items():
        if not isinstance(node, dict):
            errors.append(f"  {path.name}: node '{raw_id}' is not a dict")
            continue
        if "class_type" not in node or "inputs" not in node:
            errors.append(f"  {path.name}: node '{raw_id}' missing class_type/inputs")
            continue
        if not isinstance(node["class_type"], str):
            errors.append(f"  {path.name}: node '{raw_id}' class_type not a string")
        if not isinstance(node["inputs"], dict):
            errors.append(f"  {path.name}: node '{raw_id}' inputs not a dict")
            continue
        node_ids.add(raw_id)
        for value in node["inputs"].values():
            if isinstance(value, str):
                placeholders.update(PLACEHOLDER_RE.findall(value))

    for raw_id, node in data.items():
        for value in node.get("inputs", {}).values():
            if isinstance(value, list) and len(value) == 2:
                target, _ = value
                if str(target) not in node_ids:
                    errors.append(
                        f"  {path.name}: node '{raw_id}' references unknown node '{target}'"
                    )

    unknown = placeholders - ALLOWED_PLACEHOLDERS
    for token in sorted(unknown):
        errors.append(f"  {path.name}: placeholder {token} not in allowed contract")

    return errors


def main() -> int:
    present = {p.stem for p in WORKFLOWS_DIR.glob("*.json")}
    missing = EXPECTED_WORKFLOWS - present
    extra = present - EXPECTED_WORKFLOWS

    errors: list[str] = []
    if missing:
        errors.append(f"  missing workflows: {sorted(missing)}")
    if extra:
        errors.append(f"  unexpected workflows: {sorted(extra)}")

    for path in sorted(WORKFLOWS_DIR.glob("*.json")):
        errors.extend(validate_file(path))

    if errors:
        print("FAIL")
        for err in errors:
            print(err)
        return 1

    print("OK — all workflows valid")
    for path in sorted(WORKFLOWS_DIR.glob("*.json")):
        data = json.loads(path.read_text())
        classes = sorted({n["class_type"] for n in data.values()})
        print(f"  {path.name}: {classes}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
