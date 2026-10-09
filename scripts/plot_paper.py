#!/usr/bin/env python3
"""Generate the four results figures in the paper from aggregate_paper.py outputs."""
import argparse
import csv
from pathlib import Path
import matplotlib.pyplot as plt

STRATEGIES = ["Immediate", "Fixed", "Fixed+Jitter", "Exponential", "Exp+Jitter"]

def read(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input", default=Path("results/paper-n30"), type=Path)
    p.add_argument("--out", default=Path("results/paper-n30/figures"), type=Path)
    args=p.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    metrics=read(args.input/"paper_metrics.csv")
    depth=read(args.input/"paper_rps88_retry_depth.csv")
    figures=[
        ("successRatePct_median","Final success rate (%)","fig2_success_rate.png",(70,100)),
        ("successOnlyP99Ms_median","Success-only p99 latency (ms)","fig3_success_p99.png",(0,310)),
        ("retryAmplification_median","Retry amplification","fig4_retry_amplification.png",(0,3.7)),
    ]
    for key, ylabel, filename, ylim in figures:
        fig, ax=plt.subplots(figsize=(7,4.2),dpi=180)
        for s in STRATEGIES:
            points=sorted((r for r in metrics if r["strategy"]==s),
                          key=lambda r: float(r["baselineConflictPct"]))
            ax.plot([float(r["baselineConflictPct"]) for r in points],
                    [float(r[key]) for r in points],label=s,marker="o",linewidth=1.6)
        ax.set_xlabel("Baseline first-attempt OCC conflict rate (%)")
        ax.set_ylabel(ylabel)
        ax.set_ylim(*ylim)
        ax.grid(alpha=0.3)
        ax.legend()
        fig.tight_layout()
        fig.savefig(args.out/filename,bbox_inches="tight")
        plt.close(fig)

    categories=["success_retry_"+str(i) for i in range(6)]+["failure_exhausted"]
    labels=["0 retry","1 retry","2 retries","3 retries","4 retries","5 retries","Final failure"]
    depth=sorted(depth,key=lambda r:STRATEGIES.index(r["strategy"]))
    fig,ax=plt.subplots(figsize=(8,4.8),dpi=180)
    left=[0.0]*len(depth)
    for cat, label in zip(categories,labels):
        vals=[float(r[cat]) for r in depth]
        bars=ax.barh([r["strategy"] for r in depth],vals,left=left,label=label,height=0.65)
        for i,(bar,val) in enumerate(zip(bars,vals)):
            if val>=5:
                ax.text(left[i]+val/2,bar.get_y()+bar.get_height()/2,
                        f"{val:.2f}%",ha="center",va="center",fontsize=7)
        left=[x+v for x,v in zip(left,vals)]
    ax.set_xlim(0,100)
    ax.set_xlabel("Share of all requests (%)")
    ax.grid(axis="x",alpha=0.3)
    ax.invert_yaxis()
    ax.legend(ncol=4,frameon=False,bbox_to_anchor=(0.5,-0.18),loc="upper center")
    fig.tight_layout()
    fig.savefig(args.out/"fig5_retry_depth_all5.png",bbox_inches="tight")
    plt.close(fig)
    print("Saved four figures in",args.out)

if __name__=="__main__":
    main()

