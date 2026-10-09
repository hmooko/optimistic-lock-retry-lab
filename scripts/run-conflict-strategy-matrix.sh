#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8080}"
RATES="${RATES:?set RATES to calibrated rates, e.g. '25 35 45 55 70'}"
HOT_SET="${HOT_SET:-1}"
TX_WORK_MS="${TX_WORK_MS:-10}"
REPETITIONS="${REPETITIONS:-5}"
WARMUP="${WARMUP:-20s}"
WARMUP_DRAIN="${WARMUP_DRAIN:-10s}"
DURATION="${DURATION:-60s}"
PRE_ALLOCATED_VUS="${PRE_ALLOCATED_VUS:-1500}"
MAX_VUS="${MAX_VUS:-3000}"
OUTDIR="${OUTDIR:-results/conflict-strategy}"

STRATEGIES=(
  OPT_IMMEDIATE
  OPT_FIXED
  OPT_FIXED_JITTER
  OPT_EXPONENTIAL
  OPT_EXPONENTIAL_JITTER
)

mkdir -p "${OUTDIR}"

for repetition in $(seq 1 "${REPETITIONS}"); do
  combinations=()
  for rate in ${RATES}; do
    for strategy in "${STRATEGIES[@]}"; do
      combinations+=("${strategy}:${rate}")
    done
  done
  mapfile -t shuffled < <(printf '%s\n' "${combinations[@]}" | shuf)

  for combination in "${shuffled[@]}"; do
    strategy="${combination%%:*}"
    rate="${combination##*:}"
    output="${OUTDIR}/${strategy}_work${TX_WORK_MS}ms_hot${HOT_SET}_rps${rate}_run${repetition}.json"
    log="${OUTDIR}/${strategy}_work${TX_WORK_MS}ms_hot${HOT_SET}_rps${rate}_run${repetition}.log"

    echo "==> strategy=${strategy} tx_work_ms=${TX_WORK_MS} hot_set=${HOT_SET} rate=${rate} run=${repetition}"

    bash scripts/run-k6-docker.sh run \
      -e BASE_URL="${BASE_URL}" \
      -e RATE="${rate}" \
      -e WARMUP="${WARMUP}" \
      -e WARMUP_DRAIN="${WARMUP_DRAIN}" \
      -e DURATION="${DURATION}" \
      -e REPETITION="${repetition}" \
      -e OUTPUT="${output}" \
      -e STRATEGY="${strategy}" \
      -e HOT_SET="${HOT_SET}" \
      -e TX_WORK_MS="${TX_WORK_MS}" \
      -e MAX_RETRIES=5 \
      -e PRE_ALLOCATED_VUS="${PRE_ALLOCATED_VUS}" \
      -e MAX_VUS="${MAX_VUS}" \
      k6/benchmark.js >"${log}" 2>&1 || true

    sleep 10
  done
done
