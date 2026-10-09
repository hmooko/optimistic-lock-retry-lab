#!/usr/bin/env python3
"""Recalculate the submitted paper's n=30 statistics from structured k6 JSONs.

Each (RPS, strategy) value is the median across runs, not a pooled median.
The RPS=88 retry-depth figure alone pools request counts across runs.
"""
import argparse
import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path

BASELINE = {64: 0.57, 68: 3.23, 72: 11.38, 76: 24.99, 88: 41.01}
STRATEGIES = [
    "OPT_IMMEDIATE", "OPT_FIXED", "OPT_FIXED_JITTER",
    "OPT_EXPONENTIAL", "OPT_EXPONENTIAL_JITTER"
]
DISPLAY = {
    "OPT_IMMEDIATE": "Immediate",
    "OPT_FIXED": "Fixed",
    "OPT_FIXED_JITTER": "Fixed+Jitter",
    "OPT_EXPONENTIAL": "Exponential",
    "OPT_EXPONENTIAL_JITTER": "Exp+Jitter",
}

def write_csv(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

def percentiles(vals):
    if not vals:
        raise ValueError("empty data")
    q1, _, q3 = statistics.quantiles(vals, n=4, method="inclusive")
    return statistics.median(vals), q1, q3

def collect(directories, expected_n):
    runs = defaultdict(list)
    source_rows = []
    for folder in directories:
        files = sorted(folder.glob("*.json"))
        if not files:
            raise ValueError("No JSON files found in " + str(folder))
        seen = set()
        for path in files:
            with path.open(encoding="utf-8") as f:
                d = json.load(f)
            m, x = d["metadata"], d["metrics"]
            rate = int(m["rate"])
            strategy = m["strategy"]
            if rate not in BASELINE or strategy not in STRATEGIES:
                raise ValueError("Unexpected paper condition in " + str(path))
            if int(m["hotSet"]) != 1 or int(m["txWorkMs"]) != 10 or int(m["maxRetries"]) != 5:
                raise ValueError("Paper workload mismatch in " + str(path))
            key = (rate, strategy, int(m["repetition"]))
            if key in seen:
                raise ValueError("Duplicate condition/run within " + str(folder) + ": " + str(key))
            seen.add(key)
            if any(int(x.get(field, -1)) != 0 for field in
                   ["droppedIterations", "warmupDroppedIterations", "totalDroppedIterations"]):
                raise ValueError("Dropped iterations or missing metric in " + str(path))
            success = int(x["successCount"])
            failure = int(x["failureCount"])
            if success + failure == 0 or success == 0:
                raise ValueError("No completed/successful requests in " + str(path))
            depth = [int(v) for v in x["successfulRetryDepthCounts"]]
            if len(depth) != 6 or sum(depth) != success:
                raise ValueError("Successful retry-depth sum mismatch in " + str(path))
            row = {
                "cohort": folder.name,
                "source": path.name,
                "RPS": rate,
                "baselineConflictPct": BASELINE[rate],
                "strategy": DISPLAY[strategy],
                "repetition": int(m["repetition"]),
                "successRatePct": 100.0 * success / (success + failure),
                "successOnlyP99Ms": float(x["successP99LatencyMs"]),
                "retryAmplification": float(x["retryAmplification"]),
                "successCount": success,
                "failureCount": failure,
                "retryDepth": depth,
            }
            runs[(rate, strategy)].append(row)
            source_rows.append(row)
    expected_keys = {(r, s) for r in BASELINE for s in STRATEGIES}
    if set(runs) != expected_keys:
        raise ValueError("Missing paper conditions: " + str(expected_keys - set(runs)))
    for key, group in runs.items():
        if len(group) != expected_n:
            raise ValueError(str(key) + " has " + str(len(group)) +
                             " runs (expected " + str(expected_n) + ")")
    return runs, source_rows

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", nargs="+", required=True, type=Path,
                   help="One or more original raw-result directories")
    p.add_argument("--out", default=Path("results/paper-n30"), type=Path)
    p.add_argument("--expected-n", type=int, default=30)
    args = p.parse_args()
    runs, raw = collect(args.input, args.expected_n)
    result = []
    for rate in BASELINE:
        for strategy in STRATEGIES:
            group = runs[(rate, strategy)]
            row = {
                "baselineConflictPct": BASELINE[rate],
                "RPS": rate,
                "strategy": DISPLAY[strategy],
                "n": len(group),
            }
            for field, prefix in [
                ("successRatePct", "successRatePct"),
                ("successOnlyP99Ms", "successOnlyP99Ms"),
                ("retryAmplification", "retryAmplification")
            ]:
                med, q1, q3 = percentiles([r[field] for r in group])
                row[prefix + "_median"] = round(med, 6)
                row[prefix + "_q1"] = round(q1, 6)
                row[prefix + "_q3"] = round(q3, 6)
            result.append(row)
    summary_columns = list(result[0])
    write_csv(args.out / "paper_metrics.csv", result, summary_columns)

    pool = []
    for strategy in STRATEGIES:
        group = runs[(88, strategy)]
        depth = [sum(row["retryDepth"][i] for row in group) for i in range(6)]
        failure = sum(row["failureCount"] for row in group)
        total = failure + sum(row["successCount"] for row in group)
        row = {"strategy": DISPLAY[strategy]}
        for i, v in enumerate(depth):
            row["success_retry_" + str(i)] = round(100.0 * v / total, 6)
        row["failure_exhausted"] = round(100.0 * failure / total, 6)
        pool.append(row)
    write_csv(args.out / "paper_rps88_retry_depth.csv", pool, list(pool[0]))

    flat = []
    for r in raw:
        flat.append({k: v for k, v in r.items() if k != "retryDepth"})
    write_csv(args.out / "paper_runs.csv", flat, list(flat[0]))
    print("Validated", len(raw), "runs,",
          len(result), "conditions, n =", args.expected_n)
    print("Created", args.out / "paper_metrics.csv")
    print("Created", args.out / "paper_rps88_retry_depth.csv")
    print("Created", args.out / "paper_runs.csv")

if __name__ == "__main__":
    main()

