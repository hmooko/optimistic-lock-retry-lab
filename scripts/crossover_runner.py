#!/usr/bin/env python3
"""Crash-resumable crossover experiment: baseline OCC calibration plus 6 strategies.

Run with the final app deployment's benchmark API. The submitted paper repository
and existing raw files are NEVER modified by this script.
"""
from __future__ import annotations
import argparse
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import random
import subprocess
import sys
import time
from datetime import datetime, timezone
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
RATES = (68, 69, 70, 71, 72)
STRATEGIES = ("OPT_IMMEDIATE", "OPT_FIXED", "OPT_FIXED_JITTER",
              "OPT_EXPONENTIAL", "OPT_EXPONENTIAL_JITTER", "PESSIMISTIC")

def stamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def say(text: str) -> None:
    print(f"{stamp()} {text}", flush=True)

def parse_args():
    ap=argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["all", "calibration", "matrix", "status"],
                    default="all")
    ap.add_argument("--base-url", default="http://localhost:8080")
    ap.add_argument("--output-dir", default="results/crossover-pessimistic-n30")
    ap.add_argument("--repetitions", type=int, default=30)
    ap.add_argument("--calibration-repetitions", type=int, default=3)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-attempts", type=int, default=2)
    return ap.parse_args()

def health(base_url):
    with urlopen(base_url + "/actuator/health", timeout=7) as response:
        body=json.load(response)
    if body.get("status") != "UP":
        raise RuntimeError("APP health is not UP: " + repr(body))

def validate(path: Path, rate: int, policy: str, rep: int, cal: bool) -> dict:
    with path.open(encoding="utf-8") as fh:
        row=json.load(fh)
    m,x=row["metadata"],row["metrics"]
    expected={"strategy":policy, "rate":rate, "hotSet":1, "txWorkMs":10,
              "maxRetries":0 if cal else 5, "repetition":rep}
    for name, value in expected.items():
        if m.get(name)!=value:
            raise ValueError(f"{path}: {name} expected {value}, got {m.get(name)}")
    for name in ("droppedIterations","warmupDroppedIterations","totalDroppedIterations"):
        if int(x.get(name, -1))!=0:
            raise ValueError(f"{path}: {name}={x.get(name)}")
    completed=int(x["successCount"])+int(x["failureCount"])
    if completed<=0:
        raise ValueError(f"{path}: no complete requests")
    if cal:
        val=x.get("firstAttemptConflictRate")
        if val is None or not (0<=float(val)<=1):
            raise ValueError(f"{path}: baseline conflict rate missing")
    else:
        if int(x["successCount"])<=0:
            raise ValueError(f"{path}: no successful requests, success-only p99 cannot be calculated")
        if not math.isfinite(float(x["successP99LatencyMs"])):
            raise ValueError(f"{path}: invalid success-only p99")
        if not math.isfinite(float(x["retryAmplification"])):
            raise ValueError(f"{path}: invalid retryAmplification")
        counts=x.get("successfulRetryDepthCounts")
        if not isinstance(counts,list) or len(counts)!=6 or sum(map(int,counts))!=int(x["successCount"]):
            raise ValueError(f"{path}: retry-depth counts inconsistent")
        if policy=="PESSIMISTIC" and (int(x["retryCount"])!=0 or
                                      int(counts[0])!=int(x["successCount"])):
            raise ValueError(f"{path}: pessimistic results unexpectedly contain retries")
    return row

def run_one(args, out: Path, rate:int, policy:str, repetition:int, cal:bool):
    folder=out/("calibration" if cal else "raw")
    folder.mkdir(parents=True,exist_ok=True)
    name=f"{policy}_work10ms_hot1_rps{rate}_run{repetition}.json"
    target=folder/name
    if target.exists():
        try:
            validate(target,rate,policy,repetition,cal)
        except Exception as exc:
            raise RuntimeError(f"Existing result invalid; preserve for inspection: {target}: {exc}") from exc
        say("SKIP previously verified "+str(target))
        return

    warmup,drain,duration=("15s","5s","30s") if cal else ("20s","10s","60s")
    pre,max_vus=(500,1500) if cal else (1500,3000)
    rel=target.relative_to(ROOT).as_posix()
    k6=[
        "bash","scripts/run-k6-docker.sh","run",
        "-e",f"BASE_URL={args.base_url}",
        "-e",f"RATE={rate}",
        "-e",f"WARMUP={warmup}",
        "-e",f"WARMUP_DRAIN={drain}",
        "-e",f"DURATION={duration}",
        "-e",f"REPETITION={repetition}",
        "-e",f"OUTPUT={rel}",
        "-e",f"STRATEGY={policy}",
        "-e","HOT_SET=1",
        "-e","TX_WORK_MS=10",
        "-e",f"MAX_RETRIES={0 if cal else 5}",
        "-e",f"PRE_ALLOCATED_VUS={pre}",
        "-e",f"MAX_VUS={max_vus}",
        "k6/benchmark.js"
    ]
    for attempt in range(1,args.max_attempts+1):
        if target.exists():
            raise RuntimeError("Refusing to overwrite existing result: "+str(target))
        health(args.base_url)
        log=folder/(name+f".attempt{attempt}.log")
        say(f"START {policy} RPS={rate} run={repetition} cal={cal} attempt={attempt}")
        with log.open("w",encoding="utf-8") as dest:
            try:
                run=subprocess.run(k6,cwd=ROOT,stdout=dest,stderr=subprocess.STDOUT,
                                   timeout=600,check=False)
                code=run.returncode
            except subprocess.TimeoutExpired:
                code=124
        try:
            if code != 0:
                raise RuntimeError(f"k6 exit status {code}, see {log}")
            validate(target,rate,policy,repetition,cal)
            say(f"OK {target}")
            return
        except Exception as exc:
            say(f"INVALID {exc}")
            if target.exists():
                invalid=target.with_name(target.name+f".invalid_attempt{attempt}")
                target.rename(invalid)
            if attempt == args.max_attempts:
                raise RuntimeError(f"Exhausted {args.max_attempts} attempts, see {log}") from exc
            say("RETRY after 20-second cooldown")
            time.sleep(20)

def schedule(args):
    tasks=[]
    for rep in range(1,args.calibration_repetitions+1):
        rr=list(RATES)
        random.Random(20261009+rep).shuffle(rr)
        tasks.extend((rate,"OPT_IMMEDIATE",rep,True) for rate in rr)
    for rep in range(1,args.repetitions+1):
        combos=[(rate,policy,rep,False) for rate in RATES for policy in STRATEGIES]
        random.Random(20261101+rep).shuffle(combos)
        tasks.extend(combos)
    return tasks

def status(args,out):
    tasks=schedule(args)
    counts={"calibration":0,"matrix":0}
    bad=[]
    for rate,policy,rep,cal in tasks:
        folder=out/("calibration" if cal else "raw")
        name=f"{policy}_work10ms_hot1_rps{rate}_run{rep}.json"
        target=folder/name
        if target.is_file():
            try:
                validate(target,rate,policy,rep,cal)
                counts["calibration" if cal else "matrix"]+=1
            except Exception as exc:
                bad.append(str(exc))
    say(f"STATUS calibration={counts['calibration']}/{len(RATES)*args.calibration_repetitions}"
        f" matrix={counts['matrix']}/{len(RATES)*len(STRATEGIES)*args.repetitions}")
    if bad:
        say("INVALID FILES: "+repr(bad))
    return counts,bad

def main():
    args=parse_args()
    if args.max_attempts<1 or args.calibration_repetitions<1 or args.repetitions<1:
        raise ValueError("Repetition and attempt counts must be positive")
    out=(ROOT/args.output_dir).resolve()
    if not out.is_relative_to(ROOT/"results"):
        raise ValueError("--output-dir must be beneath the workspace results/ directory")
    if args.dry_run:
        say(f"DRY RUN: planned {len(RATES)*args.calibration_repetitions} calibration +"
            f" {len(RATES)*len(STRATEGIES)*args.repetitions} matrix runs")
        return
    if args.mode=="status":
        status(args,out)
        return
    out.mkdir(parents=True,exist_ok=True)
    lock_path=out/"run.lock"
    with lock_path.open("w") as lock:
        try:
            fcntl.flock(lock,fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("An experiment controller already holds the lock") from None
        args_path=out/"experiment_manifest.json"
        manifest={"rates":list(RATES),"strategies":list(STRATEGIES),
                  "repetitions":args.repetitions,
                  "calibrationRepetitions":args.calibration_repetitions,
                  "warmup":"20s","drain":"10s","duration":"60s",
                  "calibrationWarmup":"15s","calibrationDrain":"5s",
                  "calibrationDuration":"30s","hotSet":1,"txWorkMs":10,
                  "baseURL":args.base_url,
                  "k6Sha256":hashlib.sha256((ROOT/"k6/benchmark.js").read_bytes()).hexdigest(),
                  "createdBy":"crossover_runner.py"}
        if args_path.exists():
            old=json.loads(args_path.read_text())
            if old!=manifest:
                raise RuntimeError("Manifest changed from initial run; use new output directory")
        else:
            args_path.write_text(json.dumps(manifest,indent=2)+"\n")
        status(args,out)
        health(args.base_url)
        for rate,policy,rep,cal in schedule(args):
            if args.mode=="calibration" and not cal:
                continue
            if args.mode=="matrix" and cal:
                continue
            run_one(args,out,rate,policy,rep,cal)
            time.sleep(5 if cal else 10)
        status(args,out)
        say("ALL REQUESTED RUNS VERIFIED")
        if args.mode!="calibration":
            analysis=["python3","scripts/aggregate_crossover.py",
                      "--input",str(out),
                      "--expected-n",str(args.repetitions),
                      "--baseline-n",str(args.calibration_repetitions)]
            subprocess.run(analysis,cwd=ROOT,check=True)
            plot=["docker","run","--rm",
                  "--user",f"{os.getuid()}:{os.getgid()}",
                  "-v",f"{ROOT}:/work",
                  "-w","/work",
                  "retry-crossover-analysis:n30",
                  "scripts/plot_crossover.py",
                  "--input",str(out.relative_to(ROOT))]
            subprocess.run(plot,cwd=ROOT,check=True)
        say("COMPLETE")

if __name__=="__main__":
    try:
        main()
    except Exception as exc:
        say("FATAL: "+repr(exc))
        sys.exit(1)

