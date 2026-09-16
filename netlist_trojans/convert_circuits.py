#!/usr/bin/env python3
"""Convert infected netlists to hierarchical circuit JSON, repeatably.

Walks a tree of ``.net`` files and, for each, writes the circuit JSON next to it
(``<source>.json`` in the same directory) using pcb_qa's
``KiCadNetlistProcesser``. Re-run it after regenerating any infected netlists.

NOTE: unlike the rest of ``netlist_trojans`` (which only needs ``simp_sexp``),
this helper depends on the **pcb_qa** project package. It is kept as a separate
module and imports pcb_qa lazily, so the core stays dependency-light and this
script is the only part that needs pcb_qa on the path.

Usage (run with the project venv, from the repo root):
  .venv/bin/python -m netlist_trojans.convert_circuits
  .venv/bin/python -m netlist_trojans.convert_circuits --root outputs/Infected/SDA
  .venv/bin/python -m netlist_trojans.convert_circuits --verbose      # show parser logs
"""

import argparse
import contextlib
import glob
import logging
import os
import sys

DEFAULT_ROOT = "outputs/Infected"
DEFAULT_GLOB = "**/*.net"


@contextlib.contextmanager
def _silence_stderr():
    """Swallow skidl's KiCad-symbol / fp-lib-table warnings during conversion."""
    with open(os.devnull, "w") as devnull, contextlib.redirect_stderr(devnull):
        yield


def convert_tree(root: str = DEFAULT_ROOT, pattern: str = DEFAULT_GLOB,
                 quiet: bool = True):
    """Convert every ``.net`` under `root` matching `pattern`.

    Returns a list of (netlist_path, error_or_None). Prints one progress line
    per file to stdout.
    """
    if quiet:
        logging.disable(logging.CRITICAL)
    silence = _silence_stderr() if quiet else contextlib.nullcontext()

    with silence:
        try:
            from pcb_qa.parsers.netlist import KiCadNetlistProcesser
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                "this script needs the pcb_qa package importable — run with the "
                f"project venv from the repo root ({exc})") from exc

        nets = sorted(glob.glob(os.path.join(root, pattern), recursive=True))
        results = []
        for net in nets:
            out_dir = os.path.dirname(net) or "."
            try:
                proc = KiCadNetlistProcesser(net, output_dir=out_dir)
                proc.convert_project_netlist_to_circuit()
                proc.export_circuit_to_file()
                results.append((net, None))
                print(f"ok   {net}")
            except Exception as exc:  # noqa: BLE001
                results.append((net, exc))
                print(f"FAIL {net}: {exc!r}")

    return results


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="netlist_trojans.convert_circuits",
        description="Convert infected netlists to circuit JSON (one per .net).")
    p.add_argument("--root", default=DEFAULT_ROOT,
                   help=f"Directory tree to scan (default: {DEFAULT_ROOT})")
    p.add_argument("--glob", dest="pattern", default=DEFAULT_GLOB,
                   help=f"Glob under --root (default: {DEFAULT_GLOB})")
    p.add_argument("--verbose", action="store_true",
                   help="Show the parser/skidl logs (otherwise silenced)")
    args = p.parse_args(argv)

    try:
        results = convert_tree(args.root, args.pattern, quiet=not args.verbose)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    failures = [(n, e) for n, e in results if e is not None]
    print(f"\n{len(results) - len(failures)}/{len(results)} converted; "
          f"{len(failures)} failed")
    for net, exc in failures:
        print(f"  FAIL {net}: {exc!r}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
