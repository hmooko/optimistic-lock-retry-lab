#!/usr/bin/env python3
"""Analyze calibrated RPS 68-72, 6 policies, n=30 crossover experiment."""
from __future__ import annotations
import argparse
import csv
import json
import math
from pathlib import Path
import random
import statistics

RATES=(68,69,70,71,72)
STRATEGIES=("OPT_IMMEDIATE","OPT_FIXED","OPT_FIXED_JITTER",
            "OPT_EXPONENTIAL","OPT_EXPONENTIAL_JITTER","PESSIMISTIC")
LABEL={
 "OPT_IMMEDIATE":"Immediate",
 "OPT_FIXED":"Fixed",
 "OPT_FIXED_JITTER":"Fixed+Jitter",
 "OPT_EXPONENTIAL":"Exponential",
 "OPT_EXPONENTIAL_JITTER":"Exponential+Jitter",
 "PESSIMISTIC":"Pessimistic (FOR UPDATE)",
}

def quantile(sorted_values, x):
    if not sorted_values:
        return float("nan")
    pos=(len(sorted_values)-1)*x
    low=int(pos)
    high=min(low+1,len(sorted_values)-1)
    return sorted_values[low]*(1-(pos-low))+sorted_values[high]*(pos-low)

def median_interval(values, rnd, boots=2000):
    if not values: raise ValueError("Empty sample")
    values=[float(x) for x in values]
    estimates=sorted(statistics.median(rnd.choices(values,k=len(values))) for _ in range(boots))
    return statistics.median(values), quantile(estimates,.025), quantile(estimates,.975)

def compare_medians(a,b,rnd,boots=2000):
    a=[float(x) for x in a];b=[float(x) for x in b]
    diff=sorted(statistics.median(rnd.choices(a,k=len(a)))-
                statistics.median(rnd.choices(b,k=len(b))) for _ in range(boots))
    return statistics.median(a)-statistics.median(b),quantile(diff,.025),quantile(diff,.975)

def write(path, rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",encoding="utf-8",newline="") as f:
        if not rows: raise ValueError("No output rows")
        w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator="\n")
        w.writeheader()
        w.writerows(rows)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--input",type=Path,required=True)
    ap.add_argument("--expected-n",type=int,default=30)
    ap.add_argument("--baseline-n",type=int,default=3)
    args=ap.parse_args()
    base=args.input.resolve()
    rng=random.Random(20261009)
    cal={}
    calrows=[]
    for rps in RATES:
        values=[]
        for rep in range(1,args.baseline_n+1):
            path=base/"calibration"/f"OPT_IMMEDIATE_work10ms_hot1_rps{rps}_run{rep}.json"
            x=json.loads(path.read_text())
            assert x["metadata"]["maxRetries"]==0 and int(x["metrics"]["droppedIterations"])==0
            values.append(100*float(x["metrics"]["firstAttemptConflictRate"]))
        m,lo,hi=median_interval(values,rng)
        cal[rps]=m
        calrows.append({"RPS":rps,"n":args.baseline_n,"medianBaselineConflictPct":round(m,6),
                        "ciLow":round(lo,6),"ciHigh":round(hi,6)})
    write(base/"analysis"/"calibration.csv",calrows)

    raw={}
    runrows=[]
    for rps in RATES:
        for strategy in STRATEGIES:
            runs=[]
            for rep in range(1,args.expected_n+1):
                path=base/"raw"/f"{strategy}_work10ms_hot1_rps{rps}_run{rep}.json"
                data=json.loads(path.read_text())
                meta,x=data["metadata"],data["metrics"]
                assert meta["rate"]==rps and meta["strategy"]==strategy and meta["repetition"]==rep
                assert meta["hotSet"]==1 and meta["txWorkMs"]==10
                assert meta["maxRetries"]==5
                assert x["droppedIterations"]==0 and x["totalDroppedIterations"]==0
                success,fail=int(x["successCount"]),int(x["failureCount"])
                if success<=0 or success+fail<=0:
                    raise ValueError("Unexpected empty success count: "+str(path))
                counts=[int(z) for z in x["successfulRetryDepthCounts"]]
                assert len(counts)==6 and sum(counts)==success
                metrics={
                    "successPct":100*success/(success+fail),
                    "successOnlyP99Ms":float(x["successP99LatencyMs"]),
                    "retryAmplification":float(x["retryAmplification"]),
                    "throughputSuccessRps":float(x["throughputPerSecond"]),
                    "failurePct":100*fail/(success+fail),
                }
                if any(not math.isfinite(v) for v in metrics.values()):
                    raise ValueError("Non-finite metrics in "+str(path))
                runs.append(metrics)
                runrows.append({"RPS":rps,"baselineConflictPct":round(cal[rps],6),
                                "strategy":strategy,"repetition":rep,**metrics,
                                "successCount":success,"failureCount":fail})
            raw[(rps,strategy)]=runs
    write(base/"analysis"/"runs.csv",runrows)
    metric_keys=["successPct","successOnlyP99Ms","retryAmplification",
                 "throughputSuccessRps","failurePct"]
    summary=[]
    effects=[]
    for rps in RATES:
        baseline=raw[(rps,"OPT_IMMEDIATE")]
        for strategy in STRATEGIES:
            runs=raw[(rps,strategy)]
            row={"RPS":rps,"baselineConflictPct":round(cal[rps],6),
                 "strategy":strategy,"label":LABEL[strategy],
                 "n":len(runs)}
            effect={"RPS":rps,"baselineConflictPct":round(cal[rps],6),
                    "strategy":strategy,"n":len(runs),"comparator":"OPT_IMMEDIATE"}
            for k in metric_keys:
                val,lo,hi=median_interval([r[k] for r in runs],rng)
                row[f"{k}_median"]=round(val,6)
                row[f"{k}_ci95Low"]=round(lo,6)
                row[f"{k}_ci95High"]=round(hi,6)
                diff,dlo,dhi=compare_medians([r[k] for r in runs],[r[k] for r in baseline],rng)
                effect[f"delta_{k}_median"]=round(diff,6)
                effect[f"delta_{k}_ci95Low"]=round(dlo,6)
                effect[f"delta_{k}_ci95High"]=round(dhi,6)
            summary.append(row)
            effects.append(effect)
    write(base/"analysis"/"summary.csv",summary)
    write(base/"analysis"/"vs_immediate.csv",effects)

    findings=["Crossover comparison: 6 strategies * 5 RPS * "+str(args.expected_n)+" runs",
              "The x-axis is a separately calibrated retry-disabled OCC conflict rate.",
              "Pessimistic locking does not undergo OCC first-attempt conflicts.",
              "Bootstrap CIs use independent run resampling (percentile CI);",
              "these do not by themselves establish practical superiority or a universal threshold.",
              ""]
    for rps in RATES:
        findings.append(f"RPS {rps}; calibration conflict={cal[rps]:.3f}%")
        for s in STRATEGIES:
            x=next(v for v in summary if v["RPS"]==rps and v["strategy"]==s)
            findings.append(f"  {LABEL[s]:25s} success {x['successPct_median']:.3f}% "
                            f"p99 {x['successOnlyP99Ms_median']:.2f}ms "
                            f"retry-amp {x['retryAmplification_median']:.3f} "
                            f"success-thru {x['throughputSuccessRps_median']:.2f}RPS")
        findings.append("")
    (base/"analysis"/"summary.txt").write_text("\n".join(findings),encoding="utf-8")
    print("ANALYZED",len(runrows),"runs;",len(summary),"conditions; outputs:",base/"analysis")
    print("\n".join(findings[-9:]))

if __name__=="__main__":
    main()

