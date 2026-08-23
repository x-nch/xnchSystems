#!/usr/bin/env bash
# Phase A verification: prove the expected Prometheus series are actually
# exposed before building alerts/dashboards on top of them.
#
#   ./scripts/observability-smoke.sh                 # defaults: Node A/B LAN IPs
#   NODE_A=127.0.0.1 NODE_B=127.0.0.1 ./scripts/observability-smoke.sh
set -euo pipefail

NODE_A="${NODE_A:-192.168.50.1}"
NODE_B="${NODE_B:-192.168.50.2}"
PROMETHEUS="${PROMETHEUS:-${NODE_A}}"

failures=0
check() {
  local label="$1" url="$2" pattern="$3"
  local body
  if ! body="$(curl -fsS --max-time 5 "$url")"; then
    echo "FAIL  $label — unreachable: $url"; failures=$((failures+1)); return
  fi
  if rg -q "$pattern" <<<"$body"; then
    echo "OK    $label"
  else
    echo "FAIL  $label — series missing ($pattern) at $url"; failures=$((failures+1))
  fi
}

echo "== app /metrics =="
check "xnch http request series"      "http://${NODE_A}:8001/metrics" 'xnch_http_requests_total'
check "xnch HITL counters"            "http://${NODE_A}:8001/metrics" 'xnch_hitl_(interrupts_opened|decisions)_total'
check "xnch memory-tier gauges"       "http://${NODE_A}:8001/metrics" 'xnch_memory_tier_up'
check "nexi http request series"      "http://${NODE_B}:8000/metrics" 'nexi_http_requests_total'
check "nexi pipeline stage histogram" "http://${NODE_B}:8000/metrics" 'nexi_pipeline_stage_seconds_bucket'

echo "== exporters (if installed) =="
check "node_exporter A up"            "http://${NODE_A}:9100/metrics" 'node_exporter_build_info'
check "node_exporter B lock holder"   "http://${NODE_B}:9100/metrics" 'node_systemd_unit_state\{name="(vllm-ornith|.*vision.*media.*)\.service"'
check "dcgm-exporter B GPU metrics"   "http://${NODE_B}:9400/metrics" 'DCGM_FI_DEV_GPU_TEMP'

echo "== prometheus targets =="
if targets="$(curl -fsS --max-time 5 "http://${PROMETHEUS}:9090/api/v1/targets?state=active")"; then
  down_count="$(jq '[.data.activeTargets[] | select(.health != "up")] | length' <<<"$targets")"
  if [[ "$down_count" == "0" ]]; then echo "OK    all prometheus targets up";
  else echo "WARN  ${down_count} prometheus target(s) not up (exporters optional in Phase A)"; fi
else
  echo "FAIL  prometheus unreachable at http://${PROMETHEUS}:9090"; failures=$((failures+1))
fi

echo "== alerting (Phase B) =="
if rules="$(curl -fsS --max-time 5 "http://${PROMETHEUS}:9090/api/v1/rules")"; then
  rule_count="$(jq '[.data.groups[].rules[]] | length' <<<"$rules")"
  if (( rule_count > 0 )); then echo "OK    ${rule_count} alert rules loaded";
  else echo "FAIL  no alert rules loaded into prometheus"; failures=$((failures+1)); fi
else
  echo "FAIL  prometheus API unreachable"; failures=$((failures+1))
fi
check "alertmanager up"              "http://${PROMETHEUS}:9093/-/healthy" '.'
if am_status="$(curl -fsS --max-time 5 "http://${PROMETHEUS}:9093/api/v2/status")"; then
  echo "OK    alertmanager API responding"
else
  echo "FAIL  alertmanager API not responding"; failures=$((failures+1))
fi

echo ""
if (( failures > 0 )); then echo "${failures} check(s) FAILED"; exit 1; fi
echo "smoke checks passed"
