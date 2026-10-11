#!/usr/bin/env python3
"""Batch-run ngspice over every generated ComponentSubstitution .cir file.

Each ``.cir`` under ``outputs/Infected/ComponentSubstitution/{Value,Tolerance}``
was written by ``netlist_trojans.conversions.convert_spice`` with its own
``write ..._raw.raw all`` output path, so 803 variants of the same board don't
clobber one shared ``.raw`` file. This script just runs ``ngspice -b`` against
each one from the repo root (the ``.cir``'s ``write`` path is relative to it)
and writes an ngspice log next to the ``.cir``.

Never touches anything under ``outputs/Clean/``.

Usage (from the repo root; only needs the ``ngspice`` binary on PATH):
  .venv/bin/python -m netlist_trojans.conversions.run_spice
  .venv/bin/python -m netlist_trojans.conversions.run_spice --root outputs/Infected/ComponentSubstitution/Value
  .venv/bin/python -m netlist_trojans.conversions.run_spice --jobs 8
"""

import argparse
import concurrent.futures
import glob
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from typing import List, Optional

DEFAULT_ROOT = "outputs/Infected/ComponentSubstitution"


@dataclass
class SimResult:
    cir: str
    log: str
    raw: Optional[str]
    returncode: int
    ok: bool
    error: str


def _run_one(cir_path: str, repo_root: str) -> SimResult:
    log_path = os.path.splitext(cir_path)[0] + "_ngspice.log"
    try:
        proc = subprocess.run(
            ["ngspice", "-b", "-o", log_path, os.path.relpath(cir_path, repo_root)],
            cwd=repo_root, capture_output=True, text=True, timeout=60,
        )
        returncode = proc.returncode
    except subprocess.TimeoutExpired:
        returncode = -1

    try:
        with open(log_path) as f:
            log_text = f.read()
    except OSError:
        log_text = ""

    raw_path = None
    with open(cir_path) as f:
        for line in f:
            if line.startswith("write "):
                raw_path = line.split()[1]
                break

    error = ""
    ok = returncode == 0
    if raw_path:
        raw_abs = os.path.join(repo_root, raw_path[2:] if raw_path.startswith("./") else raw_path)
        if not os.path.exists(raw_abs):
            ok = False
            error = "no .raw written"
    if ok:
        # ngspice can exit 0 while still logging a fatal parse/model error.
        for line in log_text.splitlines():
            low = line.lower()
            if "error" in low or "fatal" in low:
                ok = False
                error = line.strip()
                break
    elif not error:
        for line in log_text.splitlines():
            if "error" in line.lower() or "fatal" in line.lower():
                error = line.strip()
                break
        if not error:
            error = f"ngspice exited {returncode}"

    return SimResult(cir=cir_path, log=log_path, raw=raw_path,
                      returncode=returncode, ok=ok, error=error)


def run(root: str, repo_root: str, jobs: int) -> List[SimResult]:
    cirs = sorted(glob.glob(os.path.join(root, "**", "*.cir"), recursive=True))
    results: List[SimResult] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as ex:
        futures = {ex.submit(_run_one, c, repo_root): c for c in cirs}
        for i, fut in enumerate(concurrent.futures.as_completed(futures), 1):
            res = fut.result()
            results.append(res)
            status = "ok  " if res.ok else "FAIL"
            print(f"[{i}/{len(cirs)}] {status} {res.cir}"
                  + (f"  ({res.error})" if not res.ok else ""))
    return results


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="netlist_trojans.conversions.run_spice",
        description="Batch-run ngspice over generated ComponentSubstitution .cir files.")
    p.add_argument("--root", default=DEFAULT_ROOT,
                   help=f"ComponentSubstitution tree to scan (default: {DEFAULT_ROOT})")
    p.add_argument("--jobs", type=int, default=8, help="Parallel ngspice processes")
    args = p.parse_args(argv)

    repo_root = os.getcwd()
    results = run(args.root, repo_root, args.jobs)
    ok = sum(1 for r in results if r.ok)
    fail = len(results) - ok
    print(f"\n{len(results)} simulation(s): {ok} ok, {fail} failed")

    manifest_path = os.path.join(args.root, "spice_run_manifest.json")
    with open(manifest_path, "w") as f:
        json.dump([asdict(r) for r in results], f, indent=2)
    print(f"Manifest: {manifest_path}")

    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
