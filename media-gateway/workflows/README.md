# ComfyUI Workflows (API format)

API-format (`/prompt`-style) ComfyUI graphs used by the media-gateway executor.
Each file is a map of node-id -> `{class_type, inputs}` with connections as
`[node_id, output_index]` arrays.

## Placeholder contract

The executor substitutes these tokens before POSTing to ComfyUI. Tokens are
UPPER_SNAKE_CASE wrapped in `< >`. Substitution is **typed** by field:
`<SEED>`/`<VIDEO_LENGTH>`/`<LAST_FRAME>` become integers, everything else a
string.

| Token | Used by | Meaning |
|-------|---------|---------|
| `<PROMPT>` | all | User text prompt (empty string for upscale = no-op text) |
| `<INPUT_IMAGE>` | img2img, inpaint, upscale, i2v, v2v | Filename in ComfyUI `input/` (images and videos both land in `input/` root — LoadImage/LoadVideo list from there) |
| `<INPUT_IMAGE2>` | inpaint | Mask filename in ComfyUI `input/` (R channel used) |
| `<OUTPUT_PREFIX>` | all | SaveImage/SaveVideo `filename_prefix` (executor sets job_id) |
| `<SEED>` | all | Integer seed (executor derives from job options or random) |
| `<VIDEO_LENGTH>` | wan_* | Integer frame count |
| `<LAST_FRAME>` | wan_v2v | Integer index of final frame for `end_image` |

## Expected model files (Node B, from start-media.sh `--download-models`)

Flux (Comfy-Org repos):
- `flux1-schnell-fp8.safetensors` — UNet (UNETLoader)
- `t5xxl_fp8_e4m3fn.safetensors`, `clip_l.safetensors` — text encoders (DualCLIPLoader)
- `ae.safetensors` — VAE

Wan 2.1 GGUF Q5 (city96) + Wan 2.1 repackaged (Comfy-Org):
- `wan2.1-t2v-14b-Q5_K_M.gguf` — UnetLoaderGGUF (t2v)
- `wan2.1-i2v-14b-480p-Q5_K_M.gguf` — UnetLoaderGGUF (i2v, and v2v reuses the i2v model)
- `umt5_xxl_fp8_e4m3fn_scaled.safetensors` — CLIPLoader (type `wan`)
- `wan_2.1_vae.safetensors` — VAE

## Node inventory

| Class | Workflows | Source |
|-------|-----------|--------|
| UNETLoader / UnetLoaderGGUF | all | core / comfyui-gguf |
| DualCLIPLoader / CLIPLoader | all | core |
| VAELoader / VAEDecode / VAEEncode | all | core |
| CLIPTextEncode | all | core |
| KSampler | all | core |
| EmptyLatentImage | flux_t2i | core |
| LoadImage / LoadImageMask | img2img, inpaint, upscale, i2v | core |
| InpaintModelConditioning | flux_inpaint | core |
| LatentUpscaleBy | flux_upscale | core |
| WanTextToVideo / WanImageToVideo / WanFirstLastFrameToVideo | wan_* | core (Wan2.x) |
| LoadVideo / GetVideoComponents / ImageFromBatch | wan_v2v | core (video ext) |
| CreateVideo / SaveVideo | wan_* | core (video ext) |

## Node B validation checklist (before step 6 e2e)

These templates are starting points — ComfyUI node signatures drift across
versions and the GGUF extension. On Node B, after the stack is up:

1. Install `comfyui-gguf` in the comfy venv (UnetLoaderGGUF).
2. Load each workflow in the ComfyUI UI, substitute `<PROMPT>`, `<INPUT_IMAGE>`,
   `<OUTPUT_PREFIX>`, `<SEED>` with real values, and `Queue Prompt`.
3. Confirm every node class exists and every input name matches the installed
   version — the Wan nodes here take the model **directly into KSampler** and
   output (positive, negative, latent); video saving goes
   `VAEDecode → CreateVideo → SaveVideo(video=...)`. `LoadVideo` lists from
   `input/` root.
4. Confirm sampler settings are sane for the installed ComfyUI: Wan `steps 20 /
   cfg 6.0 / euler / simple` and Flux schnell `steps 4 / cfg 1.0 / euler / simple`
   are defaults to verify, not gospel.
5. If a GGUF filename differs from the table above, update the `unet_name` here.
6. `python workflows/validate.py` should pass from the repo root.

`video_understand` is intentionally absent — that task is served by Qwen2.5-VL
(vLLM via LiteLLM), not ComfyUI.
