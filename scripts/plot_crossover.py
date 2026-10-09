#!/usr/bin/env python3
"""Figures for adaptive/pessimistic crossover follow-up; outputs in results/.../analysis/figures."""
from pathlib import Path
import argparse
import csv
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

STRATEGIES=["OPT_IMMEDIATE","OPT_FIXED","OPT_FIXED_JITTER",
            "OPT_EXPONENTIAL","OPT_EXPONENTIAL_JITTER","PESSIMISTIC"]
LABEL={"OPT_IMMEDIATE":"Immediate","OPT_FIXED":"Fixed",
       "OPT_FIXED_JITTER":"Fixed+Jitter","OPT_EXPONENTIAL":"Exponential",
       "OPT_EXPONENTIAL_JITTER":"Exponential+Jitter",
       "PESSIMISTIC":"Pessimistic"}

def load(path):
    with path.open(encoding="utf-8",newline="") as f:
        return list(csv.DictReader(f))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--input",type=Path,required=True)
    args=ap.parse_args()
    folder=args.input.resolve()/"analysis"
    data=load(folder/"summary.csv")
    output=folder/"figures"
    output.mkdir(parents=True,exist_ok=True)
    columns=[
        ("successPct_median","Final success rate (%)","success_rate.png"),
        ("successOnlyP99Ms_median","Success-only p99 latency (ms)","success_p99.png"),
        ("retryAmplification_median","Retry amplification","retry_amplification.png"),
        ("throughputSuccessRps_median","Successful requests / s","successful_throughput.png"),
    ]
    for column,ylabel,path in columns:
        fig,ax=plt.subplots(figsize=(8,4.7),dpi=180)
        for s in STRATEGIES:
            series=sorted((r for r in data if r["strategy"]==s),key=lambda r:int(r["RPS"]))
            xs=[float(r["baselineConflictPct"]) for r in series]
            ys=[float(r[column]) for r in series]
            ax.plot(xs,ys,marker="o",label=LABEL[s],linewidth=1.7,markersize=4)
        ax.set_xlabel("Baseline first-attempt OCC conflict (%)")
        ax.set_ylabel(ylabel)
        ax.grid(alpha=.2)
        ax.legend(fontsize=8,ncol=2)
        fig.tight_layout()
        fig.savefig(output/path,bbox_inches="tight")
        plt.close(fig)
    print("Generated",len(columns),"figures:",output)

if __name__=="__main__":
    main()

