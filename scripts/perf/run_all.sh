#!/usr/bin/env bash
# F-168: every measurement in docs/perf-feel.md, each on a fresh server and a freshly seeded trip.
#   scripts/perf/run_all.sh /tmp/ga-perf-xyz        (results: $OUT/runs.jsonl, server logs: $OUT/server-*.jsonl)
# Needs the project's pixi environment (python with playwright and chromium installed: pixi run test-browser-install).
set -euo pipefail
OUT=${1:?output folder}
HERE=$(cd "$(dirname "$0")" && pwd)
PY=${PY:-python}
PORT=${PERF_PORT:-5020}
mkdir -p "$OUT"
run() {   # form reps cpu latency tag
  local data="$OUT/data-$5"; rm -rf "$data"; mkdir -p "$data"
  PERF_DATA="$data" PERF_LOG="$OUT/server-$5.jsonl" PERF_PORT=$PORT setsid "$PY" "$HERE/serve.py" > "$OUT/serve-$5.out" 2>&1 &
  local pid=$!
  for _ in $(seq 50); do curl -sf "http://127.0.0.1:$PORT/healthz" >/dev/null && break; sleep 0.2; done
  "$PY" "$HERE/seed.py" "http://127.0.0.1:$PORT" "$OUT/state-$5.json"
  echo "{\"mark\": \"$5\", \"at\": $(date +%s.%N)}" >> "$OUT/server-$5.jsonl"
  "$PY" "$HERE/measure.py" "http://127.0.0.1:$PORT" "$OUT/state-$5.json" "$OUT/runs.jsonl" "$1" "$2" "$3" "$4"
  kill "$pid"; wait "$pid" 2>/dev/null || true
}
run phone  3 4 180 phone-cpu4-lat180
run laptop 3 4 180 laptop-cpu4-lat180
run phone  2 1 180 phone-cpu1-lat180
run laptop 2 1 180 laptop-cpu1-lat180
run phone  1 4 0   phone-cpu4-lat0
run laptop 1 4 0   laptop-cpu4-lat0
run stale  2 4 180 stale-cpu4-lat180
