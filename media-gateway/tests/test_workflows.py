"""ComfyUI workflow JSON validation tests."""
import json
import re
from pathlib import Path

WORKFLOWS_DIR = Path(__file__).resolve().parents[1] / "workflows"
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


def _load(name: str) -> dict:
    path = WORKFLOWS_DIR / f"{name}.json"
    assert path.is_file(), f"missing workflow {name}"
    return json.loads(path.read_text())


def _node_classes(name: str) -> set[str]:
    return {node["class_type"] for node in _load(name).values()}


def test_all_expected_workflows_exist():
    present = {p.stem for p in WORKFLOWS_DIR.glob("*.json")}
    assert EXPECTED_WORKFLOWS <= present


def test_workflows_are_valid_api_format():
    for name in EXPECTED_WORKFLOWS:
        data = _load(name)
        assert isinstance(data, dict)
        for raw_id, node in data.items():
            assert isinstance(node, dict)
            assert isinstance(node["class_type"], str)
            assert isinstance(node["inputs"], dict)


def test_connections_reference_existing_nodes():
    for name in EXPECTED_WORKFLOWS:
        data = _load(name)
        node_ids = set(data)
        for node in data.values():
            for value in node["inputs"].values():
                if isinstance(value, list) and len(value) == 2:
                    target, _ = value
                    assert str(target) in node_ids, f"{name}: dangling ref {target}"


def test_placeholders_within_contract():
    for name in EXPECTED_WORKFLOWS:
        data = _load(name)
        for node in data.values():
            for value in node["inputs"].values():
                if isinstance(value, str):
                    for token in PLACEHOLDER_RE.findall(value):
                        assert token in ALLOWED_PLACEHOLDERS, f"{name}: {token}"


def test_every_workflow_has_output_and_seed():
    for name in EXPECTED_WORKFLOWS:
        classes = _node_classes(name)
        assert "SaveImage" in classes or "SaveVideo" in classes, f"{name}: no output"
        assert "KSampler" in classes, f"{name}: no KSampler"


def test_flux_workflows_use_flux_nodes():
    for name in ("flux_t2i", "flux_img2img", "flux_inpaint", "flux_upscale"):
        classes = _node_classes(name)
        assert "UNETLoader" in classes
        assert "DualCLIPLoader" in classes


def test_wan_workflows_use_wan_and_gguf_nodes():
    for name in ("wan_t2v", "wan_i2v", "wan_v2v"):
        classes = _node_classes(name)
        assert "UnetLoaderGGUF" in classes
        assert "SaveVideo" in classes
        assert any(cls.startswith("Wan") for cls in classes)


def test_v2v_uses_video_input():
    data = _load("wan_v2v")
    classes = {n["class_type"] for n in data.values()}
    assert "LoadVideo" in classes
    assert "ImageFromBatch" in classes


def test_inpaint_has_mask_input():
    data = _load("flux_inpaint")
    classes = {n["class_type"] for n in data.values()}
    assert "LoadImageMask" in classes
    assert "InpaintModelConditioning" in classes
