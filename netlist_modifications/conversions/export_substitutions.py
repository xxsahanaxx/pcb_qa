#!/usr/bin/env python3
"""Re-derive every ComponentSubstitution variant from its Clean *schematic*.

The ComponentSubstitution ``.net`` files were made by splicing the Clean
``.net`` text directly (``insert_modification.value`` / ``.tolerance``), and
their ``.cir`` by patching the Clean ``.cir`` template (``convert_spice``).
This script instead makes the same substitution in the KiCad schematic and lets
``kicad-cli`` export both, the way GndShortRef variants are built:

  1. Read the substitution off the variant's existing infected ``.net`` (the
     ref's ``value`` for Value variants, its ``Tolerance`` property for
     Tolerance ones) -- that file is the spec every downstream step used.
  2. Copy the board's Clean project (``OSHP_files/Clean/...``, never written
     to) into a scratch directory and edit only the target symbol: its
     ``Value`` property, or add/update a hidden ``Tolerance`` property.
  3. ``kicad-cli`` exports the ``.net`` (kicadsexpr) and the SPICE ``.cir``.
     The ``.net`` replaces the variant's existing one; the raw SPICE export is
     kept as ``<cir stem>.kicad_cir`` and finished into a runnable deck under
     the variant's existing ``.cir`` name, exactly as
     ``convert_spice --raw-exports`` does for GndShortRef.
  4. Verify against a kicad-cli re-export of the Clean schematic: the new
     ``.net`` must differ only inside the target component's block, and carry
     the intended value/tolerance there.

Each variant keeps the edited project as ``kicad/`` (openable in KiCad, like
GndShortRef's; ~775 MB across all 803) plus a ``schematic.patch`` (unified diff
of the one edited sheet). ``--restore-kicad`` rebuilds ``kicad/`` from the
patches without re-exporting. Variants whose symbol sits on a sheet
instantiated more than once are skipped: the one shared symbol would change
every instance.

Only files under ``--root`` are written (plus the scratch directory).

Usage (run with the project venv, from the repo root):
  .venv/bin/python -m netlist_modifications.conversions.export_substitutions
  .venv/bin/python -m netlist_modifications.conversions.export_substitutions --limit 3 --dry-run
"""

import argparse
import concurrent.futures
import difflib
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional, Tuple

from ..insert_modification import core as nt
from ..insert_modification import gnd_short as gs
from ..insert_modification import gnd_short_ref as gsr
from .convert_spice import RAW_EXPORT_SUFFIX, _clean_template_for, _complete_raw_export

DEFAULT_ROOT = "outputs/Infected/ComponentSubstitution"
CATEGORIES = ("Value", "Tolerance")

_TOLERANCE_NET_RE = re.compile(r'\(property \(name "Tolerance"\) \(value "([^"]*)"\)\)')
_VALUE_NET_RE = re.compile(r'\(value "((?:[^"\\]|\\.)*)"\)')
_DESIGN_RE = re.compile(r"\(design\b")


# --------------------------------------------------------------------------- #
# Netlist helpers
# --------------------------------------------------------------------------- #

def comp_block(content: str, ref: str) -> Optional[Tuple[int, int]]:
    m = re.search(r'\(comp \(ref "' + re.escape(ref) + r'"\)', content)
    if not m:
        return None
    return m.start(), nt.find_matching_paren(content, m.start()) + 1


def comp_value(content: str, ref: str) -> Optional[str]:
    span = comp_block(content, ref)
    m = span and _VALUE_NET_RE.search(content[span[0]:span[1]])
    return m.group(1) if m else None


def comp_tolerance(content: str, ref: str) -> Optional[str]:
    span = comp_block(content, ref)
    m = span and _TOLERANCE_NET_RE.search(content[span[0]:span[1]])
    return m.group(1) if m else None


def _without(content: str, ref: str) -> str:
    """Netlist minus its (design ...) header and `ref`'s comp block."""
    m = _DESIGN_RE.search(content)
    if m:
        content = content[:m.start()] + content[nt.find_matching_paren(content, m.start()) + 1:]
    span = comp_block(content, ref)
    return content[:span[0]] + content[span[1]:] if span else content


def verify(clean_net: str, new_net: str, ref: str, category: str, target: str) -> str:
    """'' if `new_net` is `clean_net` with only `ref`'s intended change, else why not."""
    clean, new = nt.read(clean_net), nt.read(new_net)
    got = comp_value(new, ref) if category == "Value" else comp_tolerance(new, ref)
    if got != target:
        return f"{ref} {category.lower()} is {got!r}, expected {target!r}"
    if _without(clean, ref) != _without(new, ref):
        return "netlist differs from the Clean re-export outside the target component"
    return ""


# --------------------------------------------------------------------------- #
# Schematic edit
# --------------------------------------------------------------------------- #

def _escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _property_span(block: str, name: str) -> Optional[Tuple[int, int, str]]:
    m = re.search(r'\(property "' + re.escape(name) + r'" "((?:[^"\\]|\\.)*)"', block)
    if not m:
        return None
    return m.start(), nt.find_matching_paren(block, m.start()) + 1, m.group(1)


def edit_symbol(block: str, category: str, target: str) -> str:
    """Return the symbol block with its Value set, or Tolerance set/added."""
    name = "Value" if category == "Value" else "Tolerance"
    prop = _property_span(block, name)
    if prop:
        s, _, old = prop
        head = f'(property "{name}" "{old}"'
        return block[:s] + f'(property "{name}" "{_escape(target)}"' + block[s + len(head):]

    # No Tolerance property yet: add a hidden one beside Value.
    vs, ve, _ = _property_span(block, "Value")
    line_start = block.rfind("\n", 0, vs) + 1
    indent = block[line_start:vs]
    at = re.search(r"\(at [^)]*\)", block[vs:ve]).group(0)
    new = (f'\n{indent}(property "Tolerance" "{_escape(target)}"\n'
           f"{indent}\t{at}\n"
           f"{indent}\t(effects\n{indent}\t\t(font\n{indent}\t\t\t(size 1.27 1.27)\n"
           f"{indent}\t\t)\n{indent}\t\t(hide yes)\n{indent}\t)\n{indent})")
    return block[:ve] + new + block[ve:]


_COMP_TSTAMP_RE = re.compile(r'\(tstamps "([0-9a-fA-F-]+)"\)\)\s*$')
_SYMBOL_UUID_RE = re.compile(r'^\t\t\(uuid "([^"]*)"\)', re.M)


def symbol_uuid(clean_net: str, ref: str) -> str:
    """UUID of `ref`'s schematic symbol: the comp block's closing `(tstamps ...)`."""
    span = comp_block(clean_net, ref)
    if not span:
        raise ValueError(f"{ref} is not in the Clean re-export")
    m = _COMP_TSTAMP_RE.search(clean_net[span[0]:span[1]])
    if not m:
        raise ValueError(f"{ref} has no symbol tstamp in the Clean re-export")
    return m.group(1)


_HUNK_RE = re.compile(r"^@@ -(\d+)(,\d+)? \+(\d+)(,\d+)? @@", re.M)


def sheet_patch(sheet_file: str, original: str, sym: str, new_sym: str) -> str:
    """Unified diff of the sheet, computed over just the edited symbol block.

    Diffing the whole sheet with difflib takes ~4.5 s on Acorn's 1.5 MB sheet
    (and holds the GIL, stalling every worker); the edit is confined to one
    block, so diff that and shift the hunk line numbers by its offset.
    """
    offset = original.count("\n", 0, original.index(sym))
    diff = "".join(difflib.unified_diff(
        sym.splitlines(keepends=True), new_sym.splitlines(keepends=True),
        fromfile=f"a/{sheet_file}", tofile=f"b/{sheet_file}", n=2))
    return _HUNK_RE.sub(lambda m: f"@@ -{int(m.group(1)) + offset}{m.group(2) or ''} "
                                  f"+{int(m.group(3)) + offset}{m.group(4) or ''} @@", diff)


def locate_symbol(root_sch: str, ref: str, clean_net: str) -> Tuple[str, str]:
    """(sheet file, symbol block) that is `ref`; ValueError if absent or shared.

    Found by the symbol UUID the Clean re-export records for `ref`, not by
    reference text: the `(instances ...)` reference lists are unreliable --
    symbols copied from other projects keep those projects' refs (on Acorn the
    symbol that is C37 here also lists C10 under "dancing_forest", which
    `gnd_short_ref._find_on_sheet` would match), and stale unannotated `C?`
    paths linger. The netlist is the truth: the symbol is shared only if more
    than one exported component carries its UUID.
    """
    uuid = symbol_uuid(clean_net, ref)
    users = len(re.findall(r'\(tstamps "' + re.escape(uuid) + r'"\)\)', clean_net))
    if users > 1:
        raise ValueError(f"{ref}'s symbol is instantiated {users} times (sheet reused); "
                         f"editing it would change every instance")
    proj_dir = os.path.dirname(root_sch)
    for sheet in gs.walk_sheets(root_sch):
        text = nt.read(os.path.join(proj_dir, sheet.file))
        for kind, s, e in gs.top_level_blocks(text):
            if kind != "symbol":
                continue
            m = _SYMBOL_UUID_RE.search(text[s:e])
            if m and m.group(1) == uuid:
                return sheet.file, text[s:e]
    raise ValueError(f"{ref}'s symbol {uuid} is on no sheet of {os.path.basename(root_sch)}")


# --------------------------------------------------------------------------- #
# kicad-cli
# --------------------------------------------------------------------------- #

def export_spice(sch_path: str, out_path: str) -> None:
    subprocess.run([gs.kicad_cli(), "sch", "export", "netlist", "--format", "spice",
                    sch_path, "--output", out_path],
                   check=True, capture_output=True, text=True)


# --------------------------------------------------------------------------- #
# One variant
# --------------------------------------------------------------------------- #

@dataclass
class Board:
    name: str
    root_sch: str
    clean_net: str          # outputs/Clean/<board>/<stem>.net
    clean_reexport: str     # same schematic through this kicad-cli (scratch)
    clean_cir: Optional[str]


@dataclass
class Result:
    category: str
    board: str
    ref: str
    target: str = ""
    sheet: str = ""
    net: str = ""
    cir: str = ""
    status: str = ""        # ok | skipped | failed
    detail: str = ""
    dropped_cir_lines: List[str] = field(default_factory=list)


def build_variant(category: str, board: Board, ref: str, variant_dir: str,
                  scratch: str, dry_run: bool) -> Result:
    res = Result(category, board.name, ref)
    nets = glob.glob(os.path.join(variant_dir, "*.net"))
    cirs = glob.glob(os.path.join(variant_dir, "*.cir"))
    if len(nets) != 1:
        res.status, res.detail = "skipped", f"expected one .net, found {len(nets)}"
        return res
    res.net = nets[0]
    stem = os.path.splitext(os.path.basename(board.root_sch))[0]
    res.cir = cirs[0] if cirs else os.path.join(variant_dir, f"{stem}.cir")

    infected = nt.read(res.net)
    target = comp_value(infected, ref) if category == "Value" else comp_tolerance(infected, ref)
    if target is None:
        res.status, res.detail = "skipped", f"no {category.lower()} for {ref} in {res.net}"
        return res
    res.target = target

    try:
        sheet_file, sym = locate_symbol(board.root_sch, ref, nt.read(board.clean_reexport))
    except ValueError as exc:
        res.status, res.detail = "skipped", str(exc)
        return res
    res.sheet = sheet_file

    work = os.path.join(scratch, category, board.name, ref)
    if os.path.isdir(work):
        shutil.rmtree(work)
    proj = os.path.join(work, "kicad")
    new_root = gs.copy_project(board.root_sch, gs.walk_sheets(board.root_sch), proj)
    sheet_path = os.path.join(proj, sheet_file)
    original = nt.read(sheet_path)
    new_sym = edit_symbol(sym, category, target)
    nt.write(sheet_path, original.replace(sym, new_sym, 1))

    tmp_net = os.path.join(work, os.path.basename(res.net))
    tmp_cir = os.path.join(work, "export.cir")
    try:
        gs.export_netlist(new_root, tmp_net)
        export_spice(new_root, tmp_cir)
    except subprocess.CalledProcessError as exc:
        res.status, res.detail = "failed", f"kicad-cli: {(exc.stderr or exc.stdout).strip()[:300]}"
        return res
    # The exports name the scratch copy in `(source ...)` and project-local
    # library `(uri ...)`s; point them back at the Clean project they came from.
    orig_proj = os.path.abspath(os.path.dirname(board.root_sch))
    for path in (tmp_net, tmp_cir):
        text = nt.read(path)
        nt.write(path, text.replace(os.path.abspath(proj), orig_proj))

    problem = verify(board.clean_reexport, tmp_net, ref, category, target)
    if problem:
        res.status, res.detail = "failed", problem
        return res

    with open(tmp_cir) as f:
        raw_lines = f.readlines()
    deck, info = _complete_raw_export(raw_lines, res.cir, board.clean_cir)
    res.dropped_cir_lines = info.dropped
    patch = sheet_patch(sheet_file, original, sym, new_sym)

    if not dry_run:
        shutil.copyfile(tmp_net, res.net)
        with open(os.path.splitext(res.cir)[0] + RAW_EXPORT_SUFFIX, "w") as f:
            f.writelines(raw_lines)
        with open(res.cir, "w") as f:
            f.writelines(deck)
        with open(os.path.join(variant_dir, "schematic.patch"), "w") as f:
            f.write(patch)
        kicad_dir = os.path.join(variant_dir, "kicad")
        if os.path.isdir(kicad_dir):
            shutil.rmtree(kicad_dir)
        shutil.move(proj, kicad_dir)
    shutil.rmtree(work)
    res.status = "ok"
    res.detail = f"{sheet_file}: {ref} {category.lower()} -> {target!r}"
    return res


def restore_kicad(rec: dict, board: Board) -> str:
    """Rebuild `<variant>/kicad/` from the Clean project + its schematic.patch.

    For variants exported before project copies were kept. The patched sheet
    must equal the edit recomputed from scratch, so the copy is exactly what
    kicad-cli exported from. Returns '' on success, else why not.
    """
    variant_dir = os.path.dirname(rec["net"])
    kicad_dir = os.path.join(variant_dir, "kicad")
    if os.path.isdir(kicad_dir):
        shutil.rmtree(kicad_dir)
    gs.copy_project(board.root_sch, gs.walk_sheets(board.root_sch), kicad_dir)
    sheet_path = os.path.join(kicad_dir, rec["sheet"])
    original = nt.read(sheet_path)

    proc = subprocess.run(["patch", "-s", "-p1", "-d", kicad_dir, "-i",
                           os.path.abspath(os.path.join(variant_dir, "schematic.patch"))],
                          capture_output=True, text=True)
    if proc.returncode:
        shutil.rmtree(kicad_dir)
        return f"patch failed: {(proc.stdout + proc.stderr).strip()[:200]}"

    _, sym = locate_symbol(board.root_sch, rec["ref"], nt.read(board.clean_reexport))
    expected = original.replace(sym, edit_symbol(sym, rec["category"], rec["target"]), 1)
    if nt.read(sheet_path) != expected:
        shutil.rmtree(kicad_dir)
        return "patched sheet differs from the recomputed edit"
    return ""


def run_restore(root: str, scratch: str, jobs: int) -> int:
    with open(os.path.join(root, "kicad_export_manifest.json")) as f:
        manifest = [r for r in json.load(f) if r["status"] == "ok"]
    boards = load_boards(root, scratch)
    failed = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as ex:
        futures = {ex.submit(restore_kicad, r, boards[r["board"]]): r for r in manifest}
        for i, fut in enumerate(concurrent.futures.as_completed(futures), 1):
            rec, why = futures[fut], fut.result()
            failed += bool(why)
            print(f"[{i}/{len(manifest)}] {'FAIL' if why else 'ok  '} {rec['category']:9} "
                  f"{rec['board']:22} {rec['ref']:7} {why}", flush=True)
    print(f"\n{len(manifest) - failed} kicad/ project copies restored, {failed} failed")
    return 1 if failed else 0


# --------------------------------------------------------------------------- #
# Batch
# --------------------------------------------------------------------------- #

def load_boards(root: str, scratch: str) -> Dict[str, Optional[Board]]:
    boards: Dict[str, Optional[Board]] = {}
    names = sorted({d for c in CATEGORIES if os.path.isdir(os.path.join(root, c))
                    for d in os.listdir(os.path.join(root, c))
                    if os.path.isdir(os.path.join(root, c, d))})
    for name in names:
        nets = glob.glob(os.path.join("outputs/Clean", name, "*.net"))
        sch = gsr._schematic_for(nets[0]) if nets else None
        if not sch:
            print(f"SKIP board {name!r}: no Clean .net / KiCad schematic found")
            boards[name] = None
            continue
        reexport = os.path.join(scratch, "_clean", name, os.path.basename(nets[0]))
        gs.export_netlist(sch, reexport)
        boards[name] = Board(name, sch, nets[0], reexport,
                             _clean_template_for(os.path.join("outputs/Clean", name)))
    return boards


def run(root: str, scratch: str, jobs: int, dry_run: bool,
        limit: Optional[int]) -> List[Result]:
    boards = load_boards(root, scratch)
    tasks = []
    for category in CATEGORIES:
        for name, board in boards.items():
            board_dir = os.path.join(root, category, name)
            if board is None or not os.path.isdir(board_dir):
                continue
            refs = sorted(r for r in os.listdir(board_dir)
                          if os.path.isdir(os.path.join(board_dir, r)))
            tasks += [(category, board, r, os.path.join(board_dir, r)) for r in refs[:limit]]

    results: List[Result] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as ex:
        futures = [ex.submit(build_variant, c, b, r, d, scratch, dry_run)
                   for c, b, r, d in tasks]
        for i, fut in enumerate(concurrent.futures.as_completed(futures), 1):
            res = fut.result()
            results.append(res)
            print(f"[{i}/{len(tasks)}] {res.status:7} {res.category:9} "
                  f"{res.board:22} {res.ref:7} {res.detail}")
    results.sort(key=lambda r: (r.category, r.board, r.ref))
    return results


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="netlist_modifications.conversions.export_substitutions",
        description="Rebuild ComponentSubstitution .net/.cir from edited Clean schematics.")
    p.add_argument("--root", default=DEFAULT_ROOT,
                   help=f"ComponentSubstitution tree (default: {DEFAULT_ROOT})")
    p.add_argument("--jobs", type=int, default=6, help="Parallel variants")
    p.add_argument("--limit", type=int, help="At most N refs per board/category (testing)")
    p.add_argument("--scratch", help="Working directory (default: a fresh temp dir)")
    p.add_argument("--dry-run", action="store_true",
                   help="Build and verify everything, write nothing under --root")
    p.add_argument("--restore-kicad", action="store_true",
                   help="Only rebuild each variant's kicad/ project copy from its "
                        "schematic.patch (no re-export)")
    args = p.parse_args(argv)

    scratch = args.scratch or tempfile.mkdtemp(prefix="export_substitutions_")
    if args.restore_kicad:
        return run_restore(args.root, scratch, args.jobs)
    results = run(args.root, scratch, args.jobs, args.dry_run, args.limit)
    counts = {s: sum(r.status == s for r in results) for s in ("ok", "skipped", "failed")}
    print(f"\n{len(results)} variant(s): " + ", ".join(f"{v} {k}" for k, v in counts.items()))

    if not args.dry_run:
        manifest_path = os.path.join(args.root, "kicad_export_manifest.json")
        with open(manifest_path, "w") as f:
            json.dump([asdict(r) for r in results], f, indent=2)
        print(f"Manifest: {manifest_path}")
    return 1 if counts["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
