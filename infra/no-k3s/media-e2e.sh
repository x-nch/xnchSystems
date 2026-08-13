#!/usr/bin/env bash
# e2e smoke test for the Node B vision media stack.
# Uploads sample media, runs every task type through the media-gateway,
# and verifies each job reaches done with an output (file or text).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GATEWAY="${MEDIA_E2E_GATEWAY:-http://localhost:8090}"
TOKEN="${MEDIA_GATEWAY_TOKEN:-}"
TOKEN_ENV="${MEDIA_E2E_ENV:-$HOME/.xnch/media.env}"
JOB_TIMEOUT="${MEDIA_E2E_TIMEOUT:-1800}"
WORK="${MEDIA_E2E_WORK:-/tmp/media-e2e}"
PY="${PY:-python3}"
REQUIRE_VIDEO=0
KEEP=0

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

e2e smoke test for the vision media stack (qwen-vl + ComfyUI via media-gateway).

Options:
  --gateway URL      media-gateway base URL (default \$MEDIA_E2E_GATEWAY or http://localhost:8090)
  --token TOKEN      bearer token (default \$MEDIA_GATEWAY_TOKEN or sourced from \$MEDIA_E2E_ENV)
  --require-video    fail if a sample video cannot be generated (video_to_video)
  --keep             keep the scratch dir (\$WORK)
  -h, --help         show this help

Precondition: vllm-ornith.service must be stopped (3090 dedicated to this stack).
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --gateway) GATEWAY="$2"; shift 2 ;;
    --token) TOKEN="$2"; shift 2 ;;
    --require-video) REQUIRE_VIDEO=1; shift ;;
    --keep) KEEP=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
  esac
done

step() { echo ""; echo "=== $1 ==="; }
ok()   { echo "  OK  $1"; }
warn() { echo "  WARN $1"; }
fail() { echo "  FAIL $1" >&2; exit 1; }

command -v "$PY" >/dev/null || fail "missing python3 ($PY)"
command -v curl >/dev/null || fail "missing curl"

[[ -n "$TOKEN" ]] || { [[ -f "$TOKEN_ENV" ]] && source "$TOKEN_ENV"; }
[[ -n "$TOKEN" ]] || fail "no token — set MEDIA_GATEWAY_TOKEN or MEDIA_E2E_ENV"

step "Exclusivity precondition (3090 dedicated)"
if command -v systemctl >/dev/null 2>&1; then
  for svc in vllm-ornith.service nexi.service; do
    if systemctl is-active --quiet "$svc" 2>/dev/null; then
      fail "$svc is active — stop it first (the vision stack needs the 3090)"
    fi
    ok "$svc stopped"
  done
else
  warn "systemctl not found (running off Node B?) — verify vllm-ornith is stopped on Node B"
fi

step "Gateway health"
wait_http() {
  local url="$1" label="$2" max="${3:-60}"
  local i=0
  while (( i < max )); do
    if curl -sf "$url" >/dev/null 2>&1; then
      ok "$label"
      return 0
    fi
    sleep 2
    (( i += 2 )) || true
  done
  fail "$label (timeout ${max}s)"
}
wait_http "$GATEWAY/health" "media-gateway $GATEWAY" 60
if curl -sf "$GATEWAY/health" | grep -q '"enabled":false'; then
  fail "media-gateway reports disabled (worker not running)"
fi

# Best-effort local checks when running on Node B itself.
if curl -sf "http://localhost:8083/health" >/dev/null 2>&1; then
  ok "qwen-vl vLLM :8083 healthy"
fi
if curl -sf "http://localhost:8188/system_stats" >/dev/null 2>&1; then
  ok "ComfyUI :8188 healthy"
fi

mkdir -p "$WORK"
trap '[[ $KEEP -eq 1 ]] || rm -rf "$WORK"' EXIT

step "Sample media"
command -v ffmpeg >/dev/null || fail "missing ffmpeg (needed to synthesize sample media)"
ffmpeg -y -loglevel error -f lavfi -i "color=c=teal:size=640x360:duration=2" \
  -frames:v 1 "$WORK/sample.png" || fail "failed to render sample.png"
ffmpeg -y -loglevel error -f lavfi -i "color=c=navy:size=480x272:duration=3" \
  -pix_fmt yuv420p "$WORK/sample.mp4" || fail "failed to render sample.mp4"
ok "sample.png + sample.mp4 ($(du -h "$WORK/sample.png" | cut -f1) / $(du -h "$WORK/sample.mp4" | cut -f1))"

upload() {
  local f="$1"
  curl -sf -X POST -H "Authorization: Bearer $TOKEN" \
    -F "file=@$f" "$GATEWAY/media/files" \
    | "$PY" -c 'import sys,json;print(json.load(sys.stdin)["file_id"])' \
    || fail "upload failed: $f"
}

create_job() {
  local task="$1" prompt="$2" ids="$3"
  local payload
  payload=$("$PY" - "$task" "$prompt" "$ids" <<'EOF'
import json, sys
print(json.dumps({"task": sys.argv[1], "prompt": sys.argv[2], "input_file_ids": json.loads(sys.argv[3])}))
EOF
)
  curl -sf -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
    -d "$payload" "$GATEWAY/media/jobs" || fail "create job failed: $task"
}

wait_job() {
  local jid="$1" waited=0 body=""
  while (( waited < JOB_TIMEOUT )); do
    body=$(curl -sf -H "Authorization: Bearer $TOKEN" "$GATEWAY/media/jobs/$jid" || echo '{}')
    local status
    status=$("$PY" -c 'import sys,json;print(json.load(sys.stdin).get("status",""))' <<<"$body" 2>/dev/null || echo "")
    if [[ "$status" == "done" || "$status" == "failed" ]]; then
      printf '%s' "$body"
      return 0
    fi
    sleep 5
    waited=$((waited + 5))
  done
  echo "  timeout after ${JOB_TIMEOUT}s for $jid" >&2
  printf '%s' "$body"
  return 1
}

verify_job() {
  local name="$1" body="$2" jf="$WORK/_job.json"
  printf '%s' "$body" > "$jf"
  "$PY" - "$name" "$jf" <<'EOF' || fail "$name: output verification"
import json, sys
name = sys.argv[1]
job = json.load(open(sys.argv[2]))
if job["status"] != "done":
    print(f"  {name}: FAILED status={job['status']} error={job.get('error')}")
    sys.exit(1)
outs = job.get("output_files") or []
txt = job.get("result_text")
if not outs and not txt:
    print(f"  {name}: done but no output (output_files={len(outs)}, result_text empty)")
    sys.exit(1)
print(f"  {name}: OK done in {job.get('duration_ms')}ms outputs={len(outs)}")
EOF
  # Download the first output file, if any, and sanity-check bytes.
  local out_id
  out_id=$("$PY" - "$jf" <<'EOF'
import json, sys
job = json.load(open(sys.argv[1]))
outs = job.get("output_files") or []
print(outs[0]["file_id"] if outs else "")
EOF
)
  if [[ -n "$out_id" ]]; then
    curl -sf -H "Authorization: Bearer $TOKEN" -o "$WORK/$name.out" "$GATEWAY/media/files/$out_id" \
      || fail "$name: output download failed"
    [[ -s "$WORK/$name.out" ]] || fail "$name: output file is empty"
    ok "$name: downloaded $(du -h "$WORK/$name.out" | cut -f1)"
  fi
}

run_job() {
  local name="$1" task="$2" prompt="$3" ids="$4"
  step "Job: $name ($task)"
  local created jid final
  created=$(create_job "$task" "$prompt" "$ids")
  jid=$(printf '%s' "$created" | "$PY" -c 'import sys,json;print(json.load(sys.stdin)["job_id"])')
  echo "  job_id=$jid"
  final=$(wait_job "$jid")
  verify_job "$name" "$final"
}

IMG_ID=$(upload "$WORK/sample.png")
ok "uploaded sample.png as $IMG_ID"
VIDEO_ID=""
if ffmpeg -y -loglevel error -f lavfi -i "color=c=gray:size=160x90:duration=1" \
  -pix_fmt yuv420p -f null - >/dev/null 2>&1; then
  VIDEO_ID=$(upload "$WORK/sample.mp4")
  ok "uploaded sample.mp4 as $VIDEO_ID"
else
  if (( REQUIRE_VIDEO )); then
    fail "sample video unavailable and --require-video set"
  fi
  warn "sample video not usable — skipping video_to_video"
fi

run_job "understand" "understand" "Describe this image in one sentence." "[\"$IMG_ID\"]"
run_job "generate_image" "generate_image" "A tiny teal cube on a dark background, studio lighting" "[]"
run_job "edit_image" "edit_image" "Turn the input into a watercolor painting" "[\"$IMG_ID\"]"
run_job "upscale_image" "upscale_image" "" "[\"$IMG_ID\"]"
run_job "image_to_video" "image_to_video" "The scene gently rotates" "[\"$IMG_ID\"]"
run_job "text_to_video" "text_to_video" "A calm ocean wave rolling onto the shore" "[]"
if [[ -n "$VIDEO_ID" ]]; then
  run_job "video_to_video" "video_to_video" "Restyle as a hand-drawn animation" "[\"$VIDEO_ID\"]"
fi

step "Summary"
echo "  All media task types passed against $GATEWAY"
