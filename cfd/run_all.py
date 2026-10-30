#!/usr/bin/env python3
"""Orchestrate the OpenFOAM campaign (sequential, 4 MPI ranks per case).   python3 run_all.py [case-name ...]"""
import sys, os, json, time, subprocess, shutil
HERE = os.path.dirname(os.path.abspath(__file__)); ENV = os.path.join(HERE, "env.sh"); CASES = os.path.join(HERE, "cases")
ITERS = int(os.environ.get("CFD_ITERS", 700))

# name: args for make_case.py
MATRIX = {
    "iso_a3_L1": "--alpha 3 --level 1 --write-interval 100 --purge 0",
    "iso_a3_L0": "--alpha 3 --level 0",
    "iso_a3_L2": "--alpha 3 --level 2",
    "fol_dy085_dx3_L1": "--alpha 3 --level 1 --follower 0.85 3.0 --write-interval 100 --purge 0",
    "fol_dy070_dx3_L1": "--alpha 3 --level 1 --follower 0.70 3.0",
    "fol_dy100_dx3_L1": "--alpha 3 --level 1 --follower 1.00 3.0",
    "fol_dy130_dx3_L1": "--alpha 3 --level 1 --follower 1.30 3.0",
    "iso_a0_L1": "--alpha 0 --level 1", "iso_a15_L1": "--alpha 1.5 --level 1", "iso_a45_L1": "--alpha 4.5 --level 1", "iso_a6_L1": "--alpha 6 --level 1",
    "fol_dy085_dx2_L1": "--alpha 3 --level 1 --follower 0.85 2.0",
    "fol_dy085_dx45_L1": "--alpha 3 --level 1 --follower 0.85 4.5",
    "fol_dy085_dx3_L0": "--alpha 3 --level 0 --follower 0.85 3.0",
    "fol_dy085_dx3_L2": "--alpha 3 --level 2 --follower 0.85 3.0",
}
ORDER = ["iso_a3_L1", "iso_a3_L0", "fol_dy085_dx3_L1", "fol_dy070_dx3_L1", "fol_dy100_dx3_L1", "fol_dy130_dx3_L1", "iso_a0_L1", "iso_a6_L1",
         "fol_dy085_dx2_L1", "fol_dy085_dx45_L1", "fol_dy085_dx3_L0", "iso_a3_L2", "fol_dy085_dx3_L2"]


def sh(cmd, cwd, log=None):
    t = time.time()
    redir = f" > {log} 2>&1" if log else " > /dev/null 2>&1"
    r = subprocess.run(f"source {ENV}; {cmd}{redir}", shell=True, cwd=cwd, executable="/bin/bash")
    return r.returncode, time.time() - t


def run(name):
    case = os.path.join(CASES, name)
    if os.path.exists(os.path.join(case, "summary.json")):
        print("skip", name, flush=True); return
    shutil.rmtree(case, ignore_errors=True)
    rc, t0 = sh(f"python3 {HERE}/make_case.py {case} {MATRIX[name]} --iters {ITERS}", HERE)
    T = {}
    for step, cmd in (("blockMesh", "blockMesh"), ("snappy", "snappyHexMesh -overwrite"), ("checkMesh", "checkMesh"), ("decompose", "decomposePar -force"),
                      ("solve", "taskset -c 0-2 mpirun --oversubscribe -np 3 simpleFoam -parallel")):
        rc, dt = sh(cmd, case, f"log.{'simpleFoam' if step == 'solve' else step}"); T[step] = dict(rc=rc, s=dt)
        print(f"{name} {step} rc={rc} {dt:.0f}s", flush=True)
        if rc != 0 and step != "checkMesh": json.dump(T, open(os.path.join(case, "timing.json"), "w")); return
    json.dump(T, open(os.path.join(case, "timing.json"), "w"))
    r = subprocess.run([sys.executable, os.path.join(HERE, "postproc.py"), case], capture_output=True, text=True)
    open(os.path.join(case, "log.postproc"), "w").write(r.stdout + r.stderr)
    print(name, "post rc", r.returncode, flush=True)


if __name__ == "__main__":
    os.makedirs(CASES, exist_ok=True)
    for n in (sys.argv[1:] or ORDER): run(n)
