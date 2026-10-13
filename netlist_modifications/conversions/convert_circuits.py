#!/usr/bin/env python3
"""Convert infected netlists to hierarchical circuit JSON, repeatably.

Walks a tree of ``.net`` files and, for each, writes the circuit JSON next to it
(``<source>.json`` in the same directory) using pcb_qa's
``KiCadNetlistProcesser``. Re-run it after regenerating any infected netlists.

Before parsing, each netlist is sanitised (see ``_sanitise_netlist_text``):
whole lines carrying a valueless KiCad-9 flag node the SEXP reader chokes on
(e.g. ``(property (name "exclude_from_bom"))``) are dropped, and any
``(tstamps "a" "b" ...)`` node with more than one identifier is collapsed to
its first. The sanitised copy is a throwaway temp file fed to the reader; the
source ``.net`` on disk is untouched.

NOTE: unlike the rest of ``netlist_modifications`` (which only needs ``simp_sexp``),
this helper depends on the **pcb_qa** project package. It is kept as a separate
module and imports pcb_qa lazily, so the core stays dependency-light and this
script is the only part that needs pcb_qa on the path.

Usage (run with the project venv, from the repo root):
  .venv/bin/python -m netlist_modifications.conversions.convert_circuits
  .venv/bin/python -m netlist_modifications.conversions.convert_circuits --root outputs/Infected/SDA
  .venv/bin/python -m netlist_modifications.conversions.convert_circuits --verbose      # show parser logs
"""

import argparse
import contextlib
import glob
import logging
import os
import re
import sys
import tempfile

DEFAULT_ROOT = "outputs/Infected"
DEFAULT_GLOB = "**/*.net"

# KiCad 9 emits valueless flag nodes such as ``(property (name "exclude_from_bom"))``
# and ``(property (name "dnp"))`` that the s-expression reader in pcb_qa cannot
# parse. Each sits alone on its own line as a self-contained, paren-balanced node,
# so dropping the whole line removes it cleanly without disturbing the surrounding
# s-expression.
_UNPARSEABLE_KEYWORDS = ("exclude_from_bom", "dnp")

# A ``(tstamps "a" "b" ...)`` node with more than one identifier string (seen on
# components instantiated through several sheet levels). The reader expects a
# single identifier, so collapse the node to just its first. The match stops at
# the tstamps node's own closing paren, so any trailing parens on the line (e.g.
# the enclosing ``(comp ...)``'s ``)``) are preserved.
_MULTI_TSTAMPS_RE = re.compile(r'\(tstamps\s+("[^"]*")(?:\s+"[^"]*")+\)')


def _sanitise_netlist_text(text: str) -> str:
    """Normalise netlist text so the SEXP reader can parse it.

    1. Drop whole lines containing an unparseable valueless flag keyword.
    2. Collapse multi-identifier ``(tstamps ...)`` nodes to their first identifier.
    """
    if any(keyword in text for keyword in _UNPARSEABLE_KEYWORDS):
        text = "\n".join(
            line
            for line in text.splitlines()
            if not any(keyword in line for keyword in _UNPARSEABLE_KEYWORDS)
        )
    return _MULTI_TSTAMPS_RE.sub(r"(tstamps \1)", text)


@contextlib.contextmanager
def _sanitised_netlist(net: str):
    """Yield a path to `net` with unparseable lines removed.

    If nothing needs stripping, the original path is yielded untouched. Otherwise
    a temporary sanitised copy is written (latin-1, a byte-faithful round trip)
    and its path yielded, then deleted. The copy is only an input to the SEXP
    reader; the source ``.net`` on disk is never modified.
    """
    with open(net, encoding="latin_1") as fh:
        raw = fh.read()
    clean = _sanitise_netlist_text(raw)
    if clean == raw:
        yield net
        return
    tmp = tempfile.NamedTemporaryFile(
        mode="w", encoding="latin_1", suffix=".net", delete=False)
    try:
        tmp.write(clean)
        tmp.close()
        yield tmp.name
    finally:
        os.unlink(tmp.name)


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
                with _sanitised_netlist(net) as src:
                    proc = KiCadNetlistProcesser(src, output_dir=out_dir)
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
        prog="netlist_modifications.conversions.convert_circuits",
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
