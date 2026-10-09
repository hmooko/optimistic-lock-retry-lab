# Optimistic Lock Retry Lab — Submitted Paper (n=30)

This branch preserves only code needed to reproduce the submitted paper:
"낙관적 락 재시도에서 경합 수준에 따른 성공률-지연시간 Trade-off 분석".
Legacy pilots, pessimistic-lock comparisons and monitoring dashboards have
been removed. The 5 optimistic strategies and the measurement extension
from the working tree of the final study have been retained.

## Experimental conditions

- 5 strategies: OPT_IMMEDIATE, OPT_FIXED, OPT_FIXED_JITTER,
  OPT_EXPONENTIAL, OPT_EXPONENTIAL_JITTER
- HOT_SET=1, TX_WORK_MS=10 (synthetic delay within transaction)
- 5 retries maximum; fixed 20ms, exponential 5/10/20/40/80ms;
  jitter = +/-50% applied to the respective base wait
- RPS 64 / 68 / 72 / 76 / 88; original pre-retry first-attempt OCC
  conflict rates 0.57% / 3.23% / 11.38% / 24.99% / 41.01%
- 10 runs per condition in the first cohort and 20 more in the second;
  25 conditions and 750 runs total
- Each run: warmup 20s, drain 10s, measurement 60s.
  Execution order is shuffled within each repetition.

These baseline rates describe a specific workload and are not universal
contention percentages. The x-axis uses the original calibrated values.

## Provenance

Load server: experiment/conflict-rate based on 017f4ba with uncommitted
k6 success-only/failure-only latency and retry-depth measurement extensions.
App server: main 0dbfeb7 with 4 uncommitted Java changes for
maxRetries override and firstAttemptConflict. Both sets of changes
were incorporated into this branch. Removing unused pessimistic methods
does not change the 5 optimistic strategies, but the snapshot is not
byte-for-byte identical to the original full application.

## Three-server setup

Use separate Docker hosts for load (k6), app (Spring Boot/JPA), and
DB (MySQL). The pinned images and resource settings are in deploy/.
On DB and App hosts, copy .env.example to .env and set DB_HOST to the
private DB IP and secure, matching DB_PASSWORD values; set the private
MYSQL_ROOT_PASSWORD on the DB host. Do not commit .env.

On DB server:

    docker compose -f deploy/db/compose.yml up -d

On App server:

    docker compose -f deploy/app/compose.yml up -d --build
    curl http://127.0.0.1:8080/actuator/health

The admin reset API is benchmark-only and must never be public.

## Calibration (maxRetries=0, 3 repetitions)

On load server (replace APP_PRIVATE_IP):

    BASE_URL=http://APP_PRIVATE_IP:8080 \
      RATES="64 68 72 76 88" HOT_SET=1 TX_WORK_MS=10 REPETITIONS=3 \
      bash scripts/run-conflict-calibration.sh

This produces a baseline summary TSV. A different deployment may yield
different calibration results even with the same RPS.

## Repeat the n=30 study

Run both cohorts in separate output directories to preserve all files.
The driver uses the 5 optimistic strategies and MAX_RETRIES=5.

    BASE_URL=http://APP_PRIVATE_IP:8080 RATES="64 68 72 76 88" \
      HOT_SET=1 TX_WORK_MS=10 REPETITIONS=10 \
      WARMUP=20s WARMUP_DRAIN=10s DURATION=60s \
      PRE_ALLOCATED_VUS=1500 MAX_VUS=3000 \
      OUTDIR=results/work10-first10 \
      bash scripts/run-conflict-strategy-matrix.sh

    BASE_URL=http://APP_PRIVATE_IP:8080 RATES="64 68 72 76 88" \
      HOT_SET=1 TX_WORK_MS=10 REPETITIONS=20 \
      WARMUP=20s WARMUP_DRAIN=10s DURATION=60s \
      PRE_ALLOCATED_VUS=1500 MAX_VUS=3000 \
      OUTDIR=results/work10-additional20 \
      bash scripts/run-conflict-strategy-matrix.sh

## Aggregate original metrics and regenerate figures

    python3 scripts/aggregate_paper.py \
      --input results/work10-first10 results/work10-additional20 \
      --out results/paper-n30 --expected-n 30

    python3 -m pip install -r requirements-analysis.txt
    python3 scripts/plot_paper.py \
      --input results/paper-n30 --out results/paper-n30/figures

The aggregator checks all 750 JSONs, verifies consistent workload settings,
zero dropped iterations, and retry-depth totals. It produces:
- paper_metrics.csv: run-wise medians and inclusive-method IQRs
- paper_rps88_retry_depth.csv: RPS88 requests pooled over 30 runs
- paper_runs.csv: per-run flattened metrics

The compact paper-data folder contains the original 25-row metrics CSV
and 5-row pooled retry-depth CSV generated from the 750 completed runs.
Recreate the graphs from these without rerunning the 750 experiments:

    python3 scripts/plot_paper.py --input paper-data \
      --out results/original-paper-figures

The raw experimental JSONs are intentionally not included in git and remain
on the original load server at:
- ~/retry-lab/results/full-metrics-work10-10rep
- ~/retry-lab/results/full-metrics-work10-additional20

The compact CSV files do not replace raw JSONs for per-run audit.

Success rate = successful logical requests / all completed requests.
Success-only p99 = p99 latency among successful logical requests.
Retry amplification = total retry attempts / total successful requests.
Retry-depth fractions are pooled counts over all requests at RPS=88,
not medians of run-level percentages.

## Scope

This archive is only for the submitted paper. It omits old txWork
sweeps, pessimistic experiments, unrelated benchmark scripts,
monitoring services and exploratory reports.

