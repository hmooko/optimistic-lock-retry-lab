#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8080}"
RATES="${RATES:-45 50 55 60 64 68 70 72 74 76 78 80 84 88}"
REPETITIONS="${REPETITIONS:-3}"
HOT_SET="${HOT_SET:-1}"
TX_WORK_MS="${TX_WORK_MS:-10}"
WARMUP="${WARMUP:-15s}"
WARMUP_DRAIN="${WARMUP_DRAIN:-5s}"
DURATION="${DURATION:-30s}"
PRE_ALLOCATED_VUS="${PRE_ALLOCATED_VUS:-500}"
MAX_VUS="${MAX_VUS:-1500}"
OUTDIR="${OUTDIR:-results/conflict-calibration}"

mkdir -p "${OUTDIR}"

for repetition in $(seq 1 "${REPETITIONS}"); do
  mapfile -t shuffled_rates < <(printf '%s\n' ${RATES} | shuf)

  for rate in "${shuffled_rates[@]}"; do
    output="${OUTDIR}/baseline_work${TX_WORK_MS}ms_hot${HOT_SET}_rps${rate}_run${repetition}.json"
    log="${OUTDIR}/baseline_work${TX_WORK_MS}ms_hot${HOT_SET}_rps${rate}_run${repetition}.log"

    echo "==> baseline maxRetries=0 tx_work_ms=${TX_WORK_MS} hot_set=${HOT_SET} rate=${rate} run=${repetition}"

    bash scripts/run-k6-docker.sh run \
      -e BASE_URL="${BASE_URL}" \
      -e RATE="${rate}" \
      -e WARMUP="${WARMUP}" \
      -e WARMUP_DRAIN="${WARMUP_DRAIN}" \
      -e DURATION="${DURATION}" \
      -e REPETITION="${repetition}" \
      -e OUTPUT="${output}" \
      -e STRATEGY=OPT_IMMEDIATE \
      -e HOT_SET="${HOT_SET}" \
      -e TX_WORK_MS="${TX_WORK_MS}" \
      -e MAX_RETRIES=0 \
      -e PRE_ALLOCATED_VUS="${PRE_ALLOCATED_VUS}" \
      -e MAX_VUS="${MAX_VUS}" \
      k6/benchmark.js >"${log}" 2>&1 || true

    sleep 5
  done
done

python3 - "${OUTDIR}" "${REPETITIONS}" <<'PY'
import glob
import json
import os
import statistics
import sys
from collections import defaultdict

outdir = sys.argv[1]
expected_repetitions = int(sys.argv[2])
by_rate = defaultdict(list)

for path in glob.glob(os.path.join(outdir, "*.json")):
    with open(path) as f:
        d = json.load(f)
    by_rate[int(d["metadata"]["rate"])].append({
        "rep": int(d["metadata"]["repetition"]),
        "conflict": float(d["metrics"].get("firstAttemptConflictRate") or 0.0),
        "dropped": int(d["metrics"].get("droppedIterations") or 0),
        "p99": float(d["metrics"].get("p99LatencyMs") or 0.0),
        "throughput": float(d["metrics"].get("throughputPerSecond") or 0.0),
    })

detail_path = os.path.join(outdir, "runs.tsv")
summary_path = os.path.join(outdir, "summary.tsv")

with open(detail_path, "w") as f:
    f.write("rate\trepetition\tfirstAttemptConflictRate\tdropped\tp99Ms\tsuccessThroughput\n")
    for rate in sorted(by_rate):
        for row in sorted(by_rate[rate], key=lambda x: x["rep"]):
            f.write(
                f'{rate}\t{row["rep"]}\t{row["conflict"]:.6f}\t{row["dropped"]}'
                f'\t{row["p99"]:.3f}\t{row["throughput"]:.3f}\n'
            )

with open(summary_path, "w") as f:
    f.write("rate\tn\tmedianConflictRate\tminConflictRate\tmaxConflictRate\tmaxDropped\n")
    for rate in sorted(by_rate):
        rows = by_rate[rate]
        conflicts = [r["conflict"] for r in rows]
        max_dropped = max(r["dropped"] for r in rows)
        f.write(
            f"{rate}\t{len(rows)}\t{statistics.median(conflicts):.6f}"
            f"\t{min(conflicts):.6f}\t{max(conflicts):.6f}\t{max_dropped}\n"
        )

bad = [
    rate for rate, rows in by_rate.items()
    if len(rows) != expected_repetitions or any(r["dropped"] != 0 for r in rows)
]
if bad:
    raise SystemExit(f"incomplete or dropped calibration rates: {sorted(bad)}")

print(open(summary_path).read(), end="")
PY
